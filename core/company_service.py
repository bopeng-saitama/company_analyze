"""企業情報を取得するサービス"""

from typing import Dict, Any, Optional, List
import logging
import json
import asyncio

from tavily import TavilyClient

from config.settings import get_settings
from core.mcp_client import MCPClientManager

logger = logging.getLogger(__name__)

class CompanyService:
    """企業情報を取得するためのサービスクラス"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        CompanyServiceの初期化
        
        Args:
            api_key: Tavily API Key。指定されない場合は設定から読み込む
        """
        settings = get_settings()
        self.api_key = api_key or settings.get("tavily_api_key", "")
        self.client = None
        
        if self.api_key:
            self.init_client()
    
    def init_client(self) -> bool:
        """Tavilyクライアントを初期化する"""
        try:
            self.client = TavilyClient(api_key=self.api_key)
            logger.info("Tavilyクライアントを初期化しました")
            return True
        except Exception as e:
            logger.error(f"Tavilyクライアントの初期化に失敗しました: {e}")
            return False
    
    def get_company_info(self, company_name: str, search_depth: str = "basic", sections: Dict[str, bool] = None) -> Dict[str, Any]:
        """
        企業情報を取得する
        
        Args:
            company_name: 企業名またはURL
            search_depth: 検索深度 ("basic"または"advanced")
            sections: 検索するセクション
            
        Returns:
            企業情報を含む辞書
        """
        if not self.client:
            logger.error("Tavilyクライアントが初期化されていません")
            return {"error": "API キーが設定されていません"}
        
        try:
            logger.info(f"企業情報の取得開始: {company_name}")
            logger.info(f"検索深度: {search_depth}")
            
            # 企業名またはURLから検索クエリを構築
            query = company_name
            if not (query.startswith('http://') or query.startswith('https://')):
                query = f"{query} 企業情報 会社概要"
            
            logger.info(f"検索クエリ: {query}")
            
            # 基本分析の場合はTavilyのみを使用
            if search_depth == "basic":
                return self._get_basic_company_info(query)
            else:
                # 詳細分析の場合はMCPを使用した詳細検索も行う
                return self._get_detailed_company_info(company_name, query, sections)
        
        except Exception as e:
            logger.error(f"企業情報の取得中にエラーが発生しました: {str(e)}")
            return {"error": str(e)}
    
    def _get_basic_company_info(self, query: str) -> Dict[str, Any]:
        """
        Tavilyを使用して基本的な企業情報を取得する
        
        Args:
            query: 検索クエリ
            
        Returns:
            企業情報を含む辞書
        """
        try:
            # Tavilyで企業情報を取得
            logger.info("Tavily APIを呼び出し中...")
            company_info = self.client.get_company_info(
                query=query,
                search_depth="basic"
            )
            
            # 取得した情報をログに記録（機密情報が含まれないよう注意）
            try:
                info_preview = str(company_info)[:500] + "..." if len(str(company_info)) > 500 else str(company_info)
                logger.info(f"取得した企業情報プレビュー: {info_preview}")
            except:
                logger.info("企業情報のプレビューを表示できません")
            
            logger.info(f"企業情報の取得完了: {query}")
            return {"success": True, "data": company_info}
        
        except Exception as e:
            logger.error(f"基本企業情報の取得中にエラーが発生しました: {str(e)}")
            return {"error": str(e)}
    
    def _get_detailed_company_info(self, company_name: str, query: str, sections: Dict[str, bool] = None) -> Dict[str, Any]:
        """
        MCPを使用して詳細な企業情報を取得する
        
        Args:
            company_name: 企業名
            query: 検索クエリ
            sections: 検索するセクション
            
        Returns:
            企業情報を含む辞書
        """
        try:
            # 基本情報の取得
            basic_info_result = self._get_basic_company_info(query)
            if "error" in basic_info_result:
                return basic_info_result
            
            basic_info = basic_info_result["data"]
            combined_info = {}
            
            # コピーする前に辞書型であることを確認
            if isinstance(basic_info, dict):
                combined_info = basic_info.copy()  # 基本情報をコピー
            else:
                # 辞書型でない場合は新しい辞書に基本情報を格納
                combined_info = {"basic_info": basic_info}
            
            # 検索プロセスのログを記録するリスト
            search_process_log = []
            images_process_log = []
            
            # 現在のスレッドに新しいイベントループを作成
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # MCPクライアントの取得と詳細情報の検索
                mcp_client = loop.run_until_complete(MCPClientManager.get_instance())
                
                # 検索クエリの構築
                search_query = f"{company_name} 企業情報 事業内容 業績 社風 理念"
                
                # 検索の実行（セクション情報を渡す）
                logger.info(f"MCP検索を実行（セクション指定あり）: {search_query}")
                mcp_result = loop.run_until_complete(mcp_client.search(search_query, sections))
                
                # 画像の取得
                image_query = f"{company_name} ロゴ 本社 製品"
                logger.info(f"企業画像の検索を実行: {image_query}")
                images_result = loop.run_until_complete(mcp_client.get_images(image_query))
                
                # 詳細情報を追加
                if isinstance(mcp_result, dict) and mcp_result.get("success", False):
                    if "data" in mcp_result:
                        combined_info["detailed_research"] = mcp_result["data"]
                    if "process_log" in mcp_result:
                        search_process_log = mcp_result["process_log"]
                
                # 画像情報を追加
                if isinstance(images_result, dict) and images_result.get("success", False):
                    if "data" in images_result and isinstance(images_result["data"], dict):
                        # process_logキーを取得して削除
                        if "process_log" in images_result["data"]:
                            images_process_log = images_result["data"].pop("process_log", [])
                        combined_info["images"] = images_result["data"]
                    elif "data" in images_result:
                        combined_info["images"] = {"error": "画像データの形式が正しくありません"}
                    if "process_log" in images_result:
                        images_process_log = images_result["process_log"]
                
                # 検索プロセスログの統合
                combined_info["search_process_log"] = search_process_log
                combined_info["images_process_log"] = images_process_log
                
            finally:
                # イベントループを閉じる
                loop.close()
            
            return {"success": True, "data": combined_info}
        
        except Exception as e:
            logger.error(f"詳細企業情報の取得中にエラーが発生しました: {str(e)}")
            return {"error": str(e)}