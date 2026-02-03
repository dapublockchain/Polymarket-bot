"""
CTF Exchange Client for Polymarket

Handles interactions with the CTF Exchange smart contract for order execution.

Contract: 0x4bFb41dcdDBA6F0a3232F775EeaC3FD7dFa6477d
Docs: https://docs.polymarket.com
"""
from web3 import Web3
from eth_account import Account
from eth_account.signers.local import LocalAccount
from typing import Dict, Any, Optional, Tuple
from decimal import Decimal
import asyncio
from loguru import logger
from web3.types import TxReceipt, TxParams


class CTFExchangeClient:
    """
    Client for interacting with Polymarket CTF Exchange contract.

    This contract handles:
    - fillOrder: Execute a signed order
    - cancelOrder: Cancel an order
    - matchOrders: Match two orders
    """

    # CTF Exchange Contract Address on Polygon
    CONTRACT_ADDRESS = "0x4bFb41dcdDBA6F0a3232F775EeaC3FD7dFa6477d"

    # fillOrder function ABI
    FILL_ORDER_ABI = [
        {
            "inputs": [
                {"internalType": "struct Order.Order", "name": "order", "type": "tuple"},
                {"internalType": "bytes", "name": "signature", "type": "bytes"}
            ],
            "name": "fillOrder",
            "outputs": [{"internalType": "uint256", "name": "filled", "type": "uint256"}],
            "stateMutability": "nonpayable",
            "type": "function"
        }
    ]

    # Complete Order struct ABI for encoding
    ORDER_STRUCT_ABI = [
        {
            "components": [
                {"name": "maker", "type": "address"},
                {"name": "taker", "type": "address"},
                {"name": "tokenId", "type": "uint256"},
                {"name": "makerAmount", "type": "uint256"},
                {"name": "takerAmount", "type": "uint256"},
                {"name": "expiration", "type": "uint256"},
                {"name": "salt", "type": "uint256"}
            ],
            "internalType": "struct Order.Order",
            "name": "order",
            "type": "tuple"
        }
    ]

    def __init__(self, rpc_url: str, private_key: str):
        """
        Initialize CTF Exchange client.

        Args:
            rpc_url: Polygon RPC endpoint
            private_key: Private key for signing transactions
        """
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.account: LocalAccount = Account.from_key(private_key)
        self.address = self.account.address

        # Initialize contract
        self.contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.CONTRACT_ADDRESS),
            abi=self.FILL_ORDER_ABI
        )

        if not self.w3.is_connected():
            logger.error(f"Failed to connect to RPC at {rpc_url}")
            raise ConnectionError(f"Cannot connect to {rpc_url}")

        logger.info(f"✅ CTF Exchange Client initialized for {self.address}")

    async def fill_order(
        self,
        order: Dict[str, Any],
        signature: str,
        gas_limit: Optional[int] = None,
        gas_price_gwei: Optional[int] = None
    ) -> Tuple[bool, Optional[TxReceipt], Optional[str]]:
        """
        Execute a signed order on the CTF Exchange contract.

        Args:
            order: Signed order from PolymarketOrderSigner
            signature: Order signature (65 bytes)
            gas_limit: Optional gas limit (estimate if None)
            gas_price_gwei: Optional gas price in gwei (use EIP-1559 if None)

        Returns:
            Tuple of (success, receipt, error_message)
        """
        try:
            logger.info("="*60)
            logger.info("📝 Executing fillOrder on CTF Exchange")
            logger.info(f"   Token ID: {order['tokenId'][:20]}...")
            logger.info(f"   Maker Amount: {order['makerAmount']}")
            logger.info(f"   Taker Amount: {order['takerAmount']}")
            logger.info("="*60)

            # Prepare transaction
            loop = asyncio.get_event_loop()

            # Build transaction parameters
            tx_params = await self._build_fill_order_tx(
                order,
                signature,
                gas_limit,
                gas_price_gwei
            )

            # Sign transaction
            signed_tx = self.account.sign_transaction(tx_params)

            # Send transaction
            logger.info(f"🚀 Sending transaction...")
            logger.debug(f"Tx Hash: {signed_tx.hash.hex()}")

            tx_hash = await loop.run_in_executor(
                None,
                self.w3.eth.send_raw_transaction,
                signed_tx.raw_transaction
            )

            tx_hash_hex = tx_hash.hex()

            logger.info(f"⏳ Waiting for confirmation...")
            logger.info(f"   Tx Hash: {tx_hash_hex}")

            # Wait for receipt
            receipt = await loop.run_in_executor(
                None,
                self.w3.eth.wait_for_transaction_receipt,
                tx_hash,
                timeout=120  # 2 minutes
            )

            if receipt['status'] == 1:
                logger.success("="*60)
                logger.success("✅ Order filled successfully!")
                logger.success(f"   Tx Hash: {tx_hash_hex}")
                logger.success(f"   Gas Used: {receipt['gasUsed']}")
                logger.success(f"   Block: {receipt['blockNumber']}")
                logger.success("="*60)
                return True, receipt, None
            else:
                logger.error("="*60)
                logger.error("❌ Order fill failed!")
                logger.error(f"   Tx Hash: {tx_hash_hex}")
                logger.error(f"   Receipt: {receipt}")
                logger.error("="*60)
                return False, receipt, "Transaction reverted"

        except Exception as e:
            logger.error(f"❌ Error filling order: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False, None, str(e)

    async def _build_fill_order_tx(
        self,
        order: Dict[str, Any],
        signature: str,
        gas_limit: Optional[int],
        gas_price_gwei: Optional[int]
    ) -> TxParams:
        """
        Build transaction parameters for fillOrder.

        Args:
            order: Order dictionary
            signature: Order signature
            gas_limit: Optional gas limit
            gas_price_gwei: Optional gas price

        Returns:
            Transaction parameters
        """
        loop = asyncio.get_event_loop()

        # Prepare order struct
        order_tuple = (
            Web3.to_checksum_address(order['maker']),
            Web3.to_checksum_address(order['taker']),
            int(order['tokenId']),
            int(order['makerAmount']),
            int(order['takerAmount']),
            int(order['expiration']),
            int(order['salt'])
        )

        # Get nonce
        nonce = await loop.run_in_executor(
            None,
            self.w3.eth.get_transaction_count,
            self.address
        )

        # Build transaction
        tx_data = self.contract.functions.fillOrder(
            order_tuple,
            Web3.to_bytes(hexstr=signature)
        ).build_transaction({
            'from': self.address,
            'nonce': nonce,
            'chainId': 137
        })

        # Estimate gas if not provided
        if gas_limit is None:
            gas_limit = await loop.run_in_executor(
                None,
                self.w3.eth.estimate_gas,
                tx_data
            )
            # Add 20% buffer
            gas_limit = int(gas_limit * 1.2)
            logger.info(f"⛽ Estimated gas: {gas_limit}")

        tx_data['gas'] = gas_limit

        # Handle gas pricing
        if gas_price_gwei is None:
            # Use EIP-1559 if supported
            if self.w3.eth.chain_id == 137:  # Polygon supports EIP-1559
                try:
                    # Get current block
                    latest_block = await loop.run_in_executor(
                        None,
                        self.w3.eth.get_block,
                        'latest'
                    )

                    # Calculate priority fee (tip)
                    # Polygon typically has low priority fees
                    max_priority_fee_per_gas = Web3.to_wei(1, 'gwei')  # 1 gwei

                    # Calculate base fee
                    base_fee_per_gas = latest_block['baseFeePerGas']

                    # Max fee = 2 * base fee + priority fee
                    max_fee_per_gas = (base_fee_per_gas * 2) + max_priority_fee_per_gas

                    tx_data['maxPriorityFeePerGas'] = max_priority_fee_per_gas
                    tx_data['maxFeePerGas'] = max_fee_per_gas
                    tx_data['type'] = '0x2'  # EIP-1559

                    logger.info(f"⛽ Using EIP-1559 (Type 2) transaction")
                    logger.info(f"   Max Fee: {Web3.from_wei(max_fee_per_gas, 'gwei'):.2f} gwei")
                    logger.info(f"   Priority Fee: {Web3.from_wei(max_priority_fee_per_gas, 'gwei'):.2f} gwei")
                except Exception as e:
                    logger.warning(f"⚠️ EIP-1559 failed, using legacy: {e}")
                    # Fall back to legacy gas pricing
                    gas_price = self.w3.eth.gas_price
                    tx_data['gasPrice'] = gas_price
        else:
            # Use provided gas price
            tx_data['gasPrice'] = Web3.to_wei(gas_price_gwei, 'gwei')

        return tx_data

    async def get_allowance(
        self,
        token_address: str,
        spender_address: Optional[str] = None
    ) -> Decimal:
        """
        Check USDC allowance for CTF Exchange contract.

        Args:
            token_address: USDC token address
            spender_address: Spender address (defaults to CTF Exchange)

        Returns:
            Current allowance in USDC
        """
        if spender_address is None:
            spender_address = self.CONTRACT_ADDRESS

        # USDC ABI for allowance function
        usdc_abi = [
            {
                "constant": True,
                "inputs": [
                    {"name": "_owner", "type": "address"},
                    {"name": "_spender", "type": "address"}
                ],
                "name": "allowance",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            }
        ]

        loop = asyncio.get_event_loop()
        contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(token_address),
            abi=usdc_abi
        )

        allowance_wei = await loop.run_in_executor(
            None,
            contract.functions.allowance(self.address, spender_address).call
        )

        # USDC has 6 decimals
        return Decimal(allowance_wei) / Decimal("1e6")

    async def approve_usdc(
        self,
        usdc_address: str,
        amount: Optional[Decimal] = None,
        spender_address: Optional[str] = None
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Approve CTF Exchange to spend USDC.

        CRITICAL: Must be called before trading!

        Args:
            usdc_address: USDC token contract address
            amount: Amount to approve (None = unlimited)
            spender_address: Spender address (defaults to CTF Exchange)

        Returns:
            Tuple of (success, tx_hash, error_message)
        """
        try:
            logger.warning("="*60)
            logger.warning("⚠️  Approving USDC spend")
            logger.warning(f"   Contract: {spender_address or self.CONTRACT_ADDRESS}")
            logger.warning(f"   Amount: {'Unlimited' if amount is None else f'{amount} USDC'}")
            logger.warning("="*60)

            if spender_address is None:
                spender_address = self.CONTRACT_ADDRESS

            # USDC ABI for approve function
            usdc_abi = [
                {
                    "inputs": [
                        {"name": "spender", "type": "address"},
                        {"name": "amount", "type": "uint256"}
                    ],
                    "name": "approve",
                    "outputs": [{"name": "", "type": "bool"}],
                    "type": "function"
                }
            ]

            loop = asyncio.get_event_loop()
            contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(usdc_address),
                abi=usdc_abi
            )

            # Get nonce
            nonce = await loop.run_in_executor(
                None,
                self.w3.eth.get_transaction_count,
                self.address
            )

            # Build approve transaction
            # If amount is None, approve unlimited (2^256 - 1)
            if amount is None:
                amount_wei = 2**256 - 1
            else:
                amount_wei = int(amount * Decimal("1e6"))

            tx_data = contract.functions.approve(
                Web3.to_checksum_address(spender_address),
                amount_wei
            ).build_transaction({
                'from': self.address,
                'nonce': nonce,
                'chainId': 137,
                'gas': 50000  # Standard approval gas
            })

            # Use legacy gas pricing for approval
            gas_price = self.w3.eth.gas_price
            tx_data['gasPrice'] = gas_price

            # Sign and send
            signed_tx = self.account.sign_transaction(tx_data)

            logger.info("🚀 Sending approval transaction...")

            tx_hash = await loop.run_in_executor(
                None,
                self.w3.eth.send_raw_transaction,
                signed_tx.raw_transaction
            )

            tx_hash_hex = tx_hash.hex()

            logger.info(f"⏳ Waiting for approval confirmation...")
            logger.info(f"   Tx Hash: {tx_hash_hex}")

            # Wait for receipt
            receipt = await loop.run_in_executor(
                None,
                self.w3.eth.wait_for_transaction_receipt,
                tx_hash,
                timeout=120
            )

            if receipt['status'] == 1:
                logger.success("="*60)
                logger.success("✅ USDC approved successfully!")
                logger.success(f"   Tx Hash: {tx_hash_hex}")
                logger.success("="*60)
                return True, tx_hash_hex, None
            else:
                logger.error("❌ Approval failed")
                return False, None, "Approval transaction reverted"

        except Exception as e:
            logger.error(f"❌ Error approving USDC: {e}")
            return False, None, str(e)
