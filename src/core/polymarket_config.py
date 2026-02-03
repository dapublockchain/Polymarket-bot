"""
Polymarket Configuration Management

Based on https://docs.polymarket.com/quickstart/overview
"""
from typing import Dict, List, Tuple, Any, Optional
from src.core.config import Config


# Polymarket Contract Addresses on Polygon
# Based on official Polymarket documentation
POLYMARKET_CONTRACTS = {
    "polygon_chain_id": 137,
    "polygon_chain_name": "Polygon Mainnet",
    "usdc_token": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",  # USDC on Polygon
    "ctf_exchange": "0x4bFb41dcdDBA6F0a3232F775EeaC3FD7dFa6477d",  # CTF Exchange contract
    "clob_address": "0x...",  # CLOB contract address - to be verified from docs
}

# Required configuration for Polymarket integration
REQUIRED_CONFIG_ITEMS = {
    "wallet": {
        "PRIVATE_KEY": {
            "name": "钱包私钥",
            "description": "用于签名交易的 Polygon 钱包私钥",
            "env_var": "PRIVATE_KEY",
            "setup_instruction": "在 .env 文件中设置 PRIVATE_KEY=0x... (64位十六进制)",
            "validation": "non_empty_string"
        },
        "WALLET_ADDRESS": {
            "name": "钱包地址",
            "description": "从私钥派生的钱包地址",
            "env_var": "WALLET_ADDRESS",
            "setup_instruction": "设置 WALLET_ADDRESS=0x... (必须与私钥匹配)",
            "validation": "valid_ethereum_address"
        },
    },
    "network": {
        "POLYGON_RPC_URL": {
            "name": "Polygon RPC 端点",
            "description": "Polygon 网络的 RPC 节点地址",
            "env_var": "POLYGON_RPC_URL",
            "default": "https://polygon-rpc.com",
            "setup_instruction": "设置 POLYGON_RPC_URL=https://polygon-rpc.com",
            "validation": "valid_url"
        },
        "POLYGON_CHAIN_ID": {
            "name": "Polygon 链 ID",
            "description": "Polygon 主网链 ID (137)",
            "env_var": "POLYGON_CHAIN_ID",
            "default": "137",
            "setup_instruction": "设置 POLYGON_CHAIN_ID=137",
            "validation": "equals_137"
        },
    },
    "polymarket": {
        "POLYMARKET_WS_URL": {
            "name": "Polymarket WebSocket URL",
            "description": "Polymarket CLOB WebSocket 连接地址",
            "env_var": "POLYMARKET_WS_URL",
            "default": "wss://ws-subscriptions-clob.polymarket.com/ws/market",
            "setup_instruction": "设置 POLYMARKET_WS_URL=wss://ws-subscriptions-clob.polymarket.com/ws/market",
            "validation": "valid_websocket_url"
        },
    },
}


class PolymarketConfigValidator:
    """
    Validates Polymarket configuration for live trading.

    Checks wallet setup, network configuration, and Polymarket-specific settings.
    """

    @staticmethod
    def get_configuration_status() -> Dict[str, Any]:
        """
        Get status of all required configuration.

        Returns:
            Dictionary with configuration status, including:
            - valid: boolean (overall validity)
            - items: list of config items with their status
            - missing: list of missing config keys
            - invalid: list of invalid config values
            - warnings: list of warning messages
        """
        status = {
            "valid": True,
            "items": [],
            "missing": [],
            "invalid": [],
            "warnings": [],
        }

        # Check wallet configuration
        if not Config.PRIVATE_KEY:
            status["missing"].append("PRIVATE_KEY")
            status["valid"] = False
            status["items"].append({
                "key": "PRIVATE_KEY",
                "category": "wallet",
                "status": "missing",
                "name": "钱包私钥",
                "description": "未设置",
            })
        else:
            # Validate private key format (should be hex string)
            private_key = Config.PRIVATE_KEY
            if private_key.startswith("0x"):
                private_key = private_key[2:]

            if len(private_key) == 64 and all(c in "0123456789abcdefABCDEF" for c in private_key):
                status["items"].append({
                    "key": "PRIVATE_KEY",
                    "category": "wallet",
                    "status": "valid",
                    "name": "钱包私钥",
                    "description": "已配置 (64位十六进制)",
                })
            else:
                status["invalid"].append("PRIVATE_KEY")
                status["valid"] = False
                status["items"].append({
                    "key": "PRIVATE_KEY",
                    "category": "wallet",
                    "status": "invalid",
                    "name": "钱包私钥",
                    "description": "格式错误 (应为 0x 开头的 64 位十六进制)",
                })

        # Check wallet address
        if not Config.WALLET_ADDRESS:
            status["missing"].append("WALLET_ADDRESS")
            status["valid"] = False
            status["items"].append({
                "key": "WALLET_ADDRESS",
                "category": "wallet",
                "status": "missing",
                "name": "钱包地址",
                "description": "未设置",
            })
        elif Config.WALLET_ADDRESS == "0x0000000000000000000000000000000000000001":
            status["invalid"].append("WALLET_ADDRESS")
            status["valid"] = False
            status["items"].append({
                "key": "WALLET_ADDRESS",
                "category": "wallet",
                "status": "invalid",
                "name": "钱包地址",
                "description": "使用占位符地址 (需要设置真实地址)",
            })
        else:
            wallet_addr = Config.WALLET_ADDRESS
            short_addr = f"{wallet_addr[:10]}...{wallet_addr[-6:]}" if len(wallet_addr) > 16 else wallet_addr
            status["items"].append({
                "key": "WALLET_ADDRESS",
                "category": "wallet",
                "status": "valid",
                "name": "钱包地址",
                "description": f"{short_addr}",
            })

        # Check Polygon RPC URL
        if Config.POLYGON_RPC_URL:
            status["items"].append({
                "key": "POLYGON_RPC_URL",
                "category": "network",
                "status": "valid",
                "name": "Polygon RPC 端点",
                "description": f"{Config.POLYGON_RPC_URL}",
            })
        else:
            status["missing"].append("POLYGON_RPC_URL")
            status["valid"] = False
            status["items"].append({
                "key": "POLYGON_RPC_URL",
                "category": "network",
                "status": "missing",
                "name": "Polygon RPC 端点",
                "description": "未设置",
            })

        # Check Polymarket WebSocket URL
        if Config.POLYMARKET_WS_URL:
            # Validate WebSocket URL format
            ws_url = Config.POLYMARKET_WS_URL
            if ws_url.startswith("wss://") or ws_url.startswith("ws://"):
                status["items"].append({
                    "key": "POLYMARKET_WS_URL",
                    "category": "polymarket",
                    "status": "valid",
                    "name": "Polymarket WebSocket",
                    "description": f"{ws_url[:40]}..." if len(ws_url) > 40 else ws_url,
                })
            else:
                status["invalid"].append("POLYMARKET_WS_URL")
                status["valid"] = False
                status["items"].append({
                    "key": "POLYMARKET_WS_URL",
                    "category": "polymarket",
                    "status": "invalid",
                    "name": "Polymarket WebSocket",
                    "description": "格式错误 (应以 wss:// 或 ws:// 开头)",
                })
        else:
            status["missing"].append("POLYMARKET_WS_URL")
            status["valid"] = False
            status["items"].append({
                "key": "POLYMARKET_WS_URL",
                "category": "polymarket",
                "status": "missing",
                "name": "Polymarket WebSocket",
                "description": "未设置",
            })

        return status

    @staticmethod
    def get_setup_instructions() -> Dict[str, str]:
        """
        Get setup instructions for missing configuration.

        Returns:
            Dictionary mapping config keys to setup instructions
        """
        instructions = {
            "PRIVATE_KEY": "在 .env 文件中设置: PRIVATE_KEY=0x... (64位十六进制私钥)",
            "WALLET_ADDRESS": "从私钥派生地址，或在 .env 中设置: WALLET_ADDRESS=0x...",
            "POLYGON_RPC_URL": "在 .env 文件中设置: POLYGON_RPC_URL=https://polygon-rpc.com",
            "POLYMARKET_WS_URL": "在 .env 文件中设置: POLYMARKET_WS_URL=wss://ws-subscriptions-clob.polymarket.com/ws/market",
        }
        return instructions

    @staticmethod
    def get_configuration_checklist() -> List[Dict[str, Any]]:
        """
        Get complete checklist of required configuration.

        Returns:
            List of configuration items with setup instructions
        """
        checklist = []

        for category, items in REQUIRED_CONFIG_ITEMS.items():
            for key, info in items.items():
                checklist.append({
                    "key": key,
                    "category": category,
                    "name": info["name"],
                    "description": info["description"],
                    "env_var": info["env_var"],
                    "default": info.get("default"),
                    "setup_instruction": info["setup_instruction"],
                    "docs_url": "https://docs.polymarket.com/quickstart/overview",
                })

        return checklist

    @staticmethod
    def validate_wallet_balance() -> Tuple[bool, Optional[str]]:
        """
        Validate wallet has sufficient USDC balance.

        Returns:
            Tuple of (is_valid, error_message)
        """
        # TODO: Implement blockchain query to check USDC balance
        # This would involve:
        # 1. Connecting to Polygon RPC
        # 2. Querying USDC token balance
        # 3. Checking if balance >= minimum required

        # For now, return True (skip check)
        return True, None

    @staticmethod
    def validate_token_allowance() -> Tuple[bool, Optional[str]]:
        """
        Validate CTF Exchange token approval/allowance.

        Returns:
            Tuple of (is_valid, error_message)
        """
        # TODO: Implement blockchain query to check CLOB exchange allowance
        # This is critical - should verify allowance is NOT unlimited
        # Recommended: $20 allowance for Phase 1

        # For now, return True (skip check)
        return True, None
