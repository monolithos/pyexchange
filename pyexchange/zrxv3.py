# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2018 bargst
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging
from pprint import pformat
from typing import List

import pymaker
from pymaker import Wad, Address
from pymaker.token import ERC20Token
from pymaker.zrxv3 import ZrxExchangeV3, ZrxRelayerApiV3, ERC20Asset


class Order:
    def __init__(self,
                 order_id: int,
                 is_sell: bool,
                 price: Wad,
                 amount: Wad,
                 zrx_order: pymaker.zrxv3.Order):

        assert(isinstance(order_id, int))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))
        assert(isinstance(zrx_order, pymaker.zrxv3.Order))

        self.order_id = order_id
        self.is_sell = is_sell
        self.price = price
        self.amount = amount
        self.zrx_order = zrx_order

    @property
    def sell_to_buy_price(self) -> Wad:
        return self.price

    @property
    def buy_to_sell_price(self) -> Wad:
        return self.price

    @property
    def remaining_buy_amount(self) -> Wad:
        return self.amount*self.price if self.is_sell else self.amount

    @property
    def remaining_sell_amount(self) -> Wad:
        return self.amount if self.is_sell else self.amount*self.price

    def __repr__(self):
        return pformat(vars(self))


class Pair:
    def __init__(self, sell_token_address: Address, sell_token_decimals: int, buy_token_address: Address, buy_token_decimals: int):
        assert(isinstance(sell_token_address, Address))
        assert(isinstance(sell_token_decimals, int))
        assert(isinstance(buy_token_address, Address))
        assert(isinstance(buy_token_decimals, int))

        self.sell_token_address = sell_token_address
        self.sell_token_decimals = sell_token_decimals
        self.buy_token_address = buy_token_address
        self.buy_token_decimals = buy_token_decimals

        self.sell_asset = ERC20Asset(sell_token_address)
        self.buy_asset = ERC20Asset(buy_token_address)


class ZrxApiV3:
    """0x V3 API interface.

    The purpose is to be able to use `Order` class similar to the `Order` classes for traditional
    (centralized) exchanges i.e. having `amount` and `price` fields instead of `pay_token`, `pay_amount`,
    `buy_token` and `buy_amount`. It becomes very important if the tokens we are handling do not have
    `18` decimal places as in this case using `pay_amount` and `buy_amount` directly simply wouldn't work.
    """

    logger = logging.getLogger()

    def __init__(self, zrx_exchange: ZrxExchangeV3, zrx_api: ZrxRelayerApiV3):
        assert(isinstance(zrx_exchange, ZrxExchangeV3))
        assert(isinstance(zrx_api, ZrxRelayerApiV3))

        self.zrx_exchange = zrx_exchange
        self.zrx_api = zrx_api

    @staticmethod
    def _wad_to_blockchain(pair: Pair, amount: Wad, token_address: Address):
        assert(isinstance(pair, Pair))
        assert(isinstance(amount, Wad))
        assert(isinstance(token_address, Address))

        assert(token_address in [pair.buy_token_address, pair.sell_token_address])

        if token_address == pair.buy_token_address:
            return amount / Wad.from_number(10 ** (18 - pair.buy_token_decimals))

        elif token_address == pair.sell_token_address:
            return amount / Wad.from_number(10 ** (18 - pair.sell_token_decimals))

    @staticmethod
    def _blockchain_to_wad(pair: Pair, amount: Wad, token_address: Address):
        assert(isinstance(pair, Pair))
        assert(isinstance(amount, Wad))
        assert(isinstance(token_address, Address))

        assert(token_address in [pair.buy_token_address, pair.sell_token_address])

        if token_address == pair.buy_token_address:
            return amount * Wad.from_number(10 ** (18 - pair.buy_token_decimals))

        elif token_address == pair.sell_token_address:
            return amount * Wad.from_number(10 ** (18 - pair.sell_token_decimals))

    def get_balances(self, pair: Pair):
        assert(isinstance(pair, Pair))

        token_buy = ERC20Token(web3=self.zrx_exchange.web3, address=Address(pair.buy_token_address))
        token_sell = ERC20Token(web3=self.zrx_exchange.web3, address=Address(pair.sell_token_address))
        our_address = Address(self.zrx_exchange.web3.eth.defaultAccount)

        return token_sell.balance_of(our_address) * Wad.from_number(10 ** (18 - pair.sell_token_decimals)), \
               token_buy.balance_of(our_address) * Wad.from_number(10 ** (18 - pair.buy_token_decimals))

    def get_orders(self, pair: Pair, zrx_orders: list) -> List[Order]:
        assert(isinstance(pair, Pair))

        result = []

        for zrx_order in zrx_orders:
            is_sell = zrx_order.buy_asset == pair.buy_asset and zrx_order.pay_asset == pair.sell_asset
            is_buy = zrx_order.buy_asset == pair.sell_asset and zrx_order.pay_asset == pair.buy_asset

            if is_sell or is_buy:
                amount = zrx_order.remaining_sell_amount if is_sell else zrx_order.remaining_buy_amount
                price = zrx_order.buy_to_sell_price if is_sell else zrx_order.sell_to_buy_price

                result.append(Order(order_id=zrx_order.order_id,
                                    is_sell=is_sell,
                                    price=price / Wad.from_number(10 ** (pair.buy_token_decimals - pair.sell_token_decimals)),
                                    amount=self._blockchain_to_wad(pair, amount, pair.sell_token_address),
                                    zrx_order=zrx_order))

        return result

    def place_order(self, pair: Pair, is_sell: bool, price: Wad, amount: Wad, expiration: int) -> pymaker.zrxv3.Order:
        assert(isinstance(pair, Pair))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))
        assert(isinstance(expiration, int))

        pay_token = pair.sell_token_address if is_sell else pair.buy_token_address
        pay_amount = amount if is_sell else amount * price

        buy_token = pair.buy_token_address if is_sell else pair.sell_token_address
        buy_amount = amount * price if is_sell else amount

        order = self.zrx_exchange.create_order(pay_asset=ERC20Asset(pay_token),
                                               pay_amount=self._wad_to_blockchain(pair, pay_amount, pay_token),
                                               buy_asset=ERC20Asset(buy_token),
                                               buy_amount=self._wad_to_blockchain(pair, buy_amount, buy_token),
                                               expiration=expiration)
        order = self.zrx_api.configure_order(order)
        order = self.zrx_exchange.sign_order(order)

        if self.zrx_api.submit_order(order):
            return order
        else:
            return None
