"""MCPクライアント実装"""

import logging
import json
import asyncio
import subprocess
import os
import sys
from typing import Dict, Any, Optional, List

# プロジェクトのルートディレクトリをPythonパスに追加
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from contextlib import AsyncExitStack

from config.settings import get_settings

logger = logging.getLogger(__name__)

class MCPClient:
    """MCPサーバーと通信するためのクライアント"""
    
    def __init__(self):
        """MCPClientの初期化"""
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.server_process = None
        self.connected = False
    
    async def connect_to_server(self, server_script_path: str) -> bool:
        """
        MCPサーバーに接続する
        
        Args:
            server_script_path: サーバースクリプトのパス
            
        Returns:
            接続が成功したかどうか
        """
        try:
            # サーバースクリプトのパスを確認
            if not os.path.exists(server_script_path):
                logger.error(f"サーバースクリプトが見つかりません: {server_script_path}")
                return False
            
            # サーバーパラメータの設定
            server_params = StdioServerParameters(
                command=sys.executable,  # Pythonインタープリタ
                args=[server_script_path],
                env=None
            )

            # サーバーへの接続
            logger.info(f"MCPサーバーに接続中: {server_script_path}")
            stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
            self.stdio, self.write = stdio_transport
            self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

            # サーバーの初期化
            await self.session.initialize()

            # 利用可能なツールの一覧取得
            response = await self.session.list_tools()
            tools = response.tools
            logger.info(f"サーバー接続完了。利用可能なツール: {[tool.name for tool in tools]}")
            
            self.connected = True
            return True
            
        except Exception as e:
            logger.error(f"MCPサーバーへの接続に失敗しました: {str(e)}")
            return False
    
    async def search(self, query: str, sections: Dict[str, bool] = None) -> Dict[str, Any]:
        """
        検索ツールを使用して情報を検索する
        
        Args:
            query: 検索クエリ
            sections: 検索するセクション
            
        Returns:
            検索結果を含む辞書
        """
        if not self.connected or not self.session:
            logger.error("MCPサーバーに接続されていません")
            return {"error": "サーバーに接続されていません"}
        
        try:
            logger.info(f"検索実行: {query}")
            
            # 検索パラメータ
            search_params = {"query": query}
            
            # セクション情報があれば追加
            if sections:
                search_params["sections"] = sections
            
            # 検索の実行
            result = await self.session.call_tool("search", search_params)
            logger.info("検索完了")
            
            # JSONレスポンスを解析
            try:
                data = json.loads(result.content[0].text)
                # データ構造の検証
                if isinstance(data, dict):
                    content = data.get("content", "")
                    process_log = data.get("process_log", [])
                    
                    return {
                        "success": True, 
                        "data": content,
                        "process_log": process_log
                    }
                else:
                    logger.warning(f"検索結果が辞書型ではありません: {type(data)}")
                    return {
                        "success": True, 
                        "data": str(data),
                        "process_log": []
                    }
            except json.JSONDecodeError:
                # JSONでない場合はテキストをそのまま返す
                logger.warning("検索結果のJSON解析に失敗しました。テキストをそのまま返します。")
                return {
                    "success": True, 
                    "data": result.content[0].text,
                    "process_log": []
                }
            
        except Exception as e:
            logger.error(f"検索中にエラーが発生しました: {str(e)}")
            return {"error": str(e)}
    
    async def get_images(self, query: str) -> Dict[str, Any]:
        """
        画像を検索して取得する
        
        Args:
            query: 検索クエリ
            
        Returns:
            画像情報を含む辞書
        """
        if not self.connected or not self.session:
            logger.error("MCPサーバーに接続されていません")
            return {"error": "サーバーに接続されていません"}
        
        try:
            logger.info(f"画像検索実行: {query}")
            result = await self.session.call_tool("get_images", {"query": query})
            
            # 結果をJSONとして解析
            try:
                # 安全なJSON解析のために'をダブルクォートに置換
                text = result.content[0].text.replace("'", "\"")
                data = json.loads(text)
                
                # データの検証
                if not isinstance(data, dict):
                    logger.warning(f"画像検索結果が辞書型ではありません: {type(data)}")
                    return {
                        "success": True,
                        "data": {"error": "データ形式が正しくありません"},
                        "process_log": []
                    }
                
                # プロセスログを抽出
                process_log = []
                if "process_log" in data:
                    process_log = data.pop("process_log", [])
                
                logger.info(f"画像検索完了: {len(data)} 件の結果")
                return {
                    "success": True, 
                    "data": data,
                    "process_log": process_log
                }
            except json.JSONDecodeError as e:
                logger.error(f"画像結果のJSON解析に失敗しました: {e}, テキスト: {result.content[0].text[:100]}...")
                return {
                    "success": True, 
                    "data": {"error": "結果の解析に失敗しました"},
                    "process_log": []
                }
            
        except Exception as e:
            logger.error(f"画像検索中にエラーが発生しました: {str(e)}")
            return {"error": str(e)}
    
    async def close(self):
        """クライアントを閉じる"""
        try:
            if self.connected:
                await self.exit_stack.aclose()
                logger.info("MCPクライアントを閉じました")
        except Exception as e:
            logger.error(f"MCPクライアントを閉じる際にエラーが発生しました: {str(e)}")

class MCPClientManager:
    """MCPClientのシングルトンインスタンスを管理するクラス"""
    
    _instance: Optional[MCPClient] = None
    _initialized = False
    
    @classmethod
    async def get_instance(cls) -> MCPClient:
        """
        MCPClientのシングルトンインスタンスを取得または初期化する
        
        Returns:
            MCPClientインスタンス
        """
        if cls._instance is None:
            cls._instance = MCPClient()
            
            if not cls._initialized:
                # MCPサーバーへの接続
                script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "core", "mcp_search.py")
                await cls._instance.connect_to_server(script_path)
                cls._initialized = True
        
        return cls._instance
    
    @classmethod
    async def close(cls):
        """シングルトンインスタンスを閉じる"""
        if cls._instance is not None:
            await cls._instance.close()
            cls._instance = None
            cls._initialized = False