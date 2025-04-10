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
    
    def get_company_info(self, company_name: str, search_depth: str = "basic") -> Dict[str, Any]:
        """
        企業情報を取得する
        
        Args:
            company_name: 企業名またはURL
            search_depth: 検索深度 ("basic"または"advanced")
            
        Returns:
            企業情報を含む辞書
        """
        if not self.client:
            logger.error("Tavilyクライアントが初期化されていません")
            return {"error": "API キーが設定されていません"}
        
        try:
            logger.info(f"企業情報の取得開始: {company_name}")
            logger.info(f"検索深度: {search_depth}")
            
            # 企業名が公式サイトURLの場合はそのまま使用、それ以外は検索クエリを構築
            if company_name.startswith(('http://', 'https://')):
                # URLが直接指定された場合
                company_url = company_name
                # URL から企業名を抽出する試み
                from urllib.parse import urlparse
                domain = urlparse(company_url).netloc
                company_query = domain.split('.')[-2] if len(domain.split('.')) > 1 else domain
            else:
                # 企業名が指定された場合
                company_query = company_name
                company_url = None
            
            # 基本分析の場合はTavilyのみを使用
            if search_depth == "basic":
                return self._get_basic_company_info(company_query, company_url)
            else:
                # 詳細分析の場合はMCPを使用した詳細検索も行う
                return self._get_detailed_company_info(company_name)
        
        except Exception as e:
            logger.error(f"企業情報の取得中にエラーが発生しました: {str(e)}")
            return {"error": str(e)}
    
    def _get_basic_company_info(self, query: str, url: Optional[str] = None) -> Dict[str, Any]:
        """
        Tavilyを使用して基本的な企業情報を取得する
        
        Args:
            query: 検索クエリ
            url: 企業のURL（指定されている場合）
            
        Returns:
            企業情報を含む辞書
        """
        try:
            search_query = f"{query} 企業情報 会社概要 代表取締役"
            
            # Tavilyでの検索
            logger.info("Tavily APIを呼び出し中...")
            
            if url:
                # URLが指定されている場合、そのURLからの抽出を試みる
                try:
                    extract_response = self.client.extract(
                        urls=[url],
                        extract_depth="advanced",
                        include_images=True
                    )
                    
                    # 抽出結果を整形
                    if "results" in extract_response and extract_response["results"]:
                        result = extract_response["results"][0]
                        extracted_info = {
                            "url": url,
                            "title": result.get("title", ""),
                            "content": result.get("content", ""),
                            "images": result.get("images", [])
                        }
                        logger.info(f"URLから情報を抽出しました: {url}")
                        return {"success": True, "data": extracted_info}
                except Exception as extract_error:
                    logger.error(f"URLからの抽出に失敗しました: {extract_error}, 通常の検索に切り替えます")
            
            # 通常の検索
            company_info = self.client.search(
                query=search_query,
                search_depth="advanced",
                max_results=8
            )
            
            # Tavilyから取得したURLのリスト
            urls = []
            if "results" in company_info:
                for result in company_info["results"]:
                    if "url" in result:
                        urls.append(result["url"])
            
            # URLが存在する場合、抽出APIを使用してコンテンツを取得
            if urls:
                try:
                    # 最大3つのURLからコンテンツを抽出
                    extract_urls = urls[:3]
                    extract_response = self.client.extract(
                        urls=extract_urls,
                        extract_depth="advanced",
                        include_images=True
                    )
                    
                    if "results" in extract_response:
                        extracted_contents = []
                        for result in extract_response["results"]:
                            extracted_contents.append({
                                "url": result.get("url", ""),
                                "title": result.get("title", ""),
                                "content": result.get("content", ""),
                                "images": result.get("images", [])
                            })
                        
                        # 抽出したコンテンツを返す
                        if extracted_contents:
                            logger.info(f"{len(extracted_contents)}件のURLからコンテンツを抽出しました")
                            return {"success": True, "data": {
                                "search_results": company_info,
                                "extracted_contents": extracted_contents
                            }}
                except Exception as extract_error:
                    logger.error(f"コンテンツ抽出に失敗しました: {extract_error}")
            
            # 抽出に失敗した場合は検索結果のみを返す
            logger.info(f"基本的な検索結果を返します")
            return {"success": True, "data": company_info}
        
        except Exception as e:
            logger.error(f"基本企業情報の取得中にエラーが発生しました: {e}")
            return {"error": str(e)}
    
    def _get_detailed_company_info(self, company_name: str) -> Dict[str, Any]:
        """
        MCPを使用して詳細な企業情報を取得する
        
        Args:
            company_name: 企業名
            
        Returns:
            企業情報を含む辞書
        """
        try:
            # 現在のスレッドに新しいイベントループを作成
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # MCPクライアントの取得と詳細情報の検索
                mcp_client = loop.run_until_complete(MCPClientManager.get_instance())
                
                # 検索の実行
                logger.info(f"MCP詳細検索を実行: {company_name}")
                mcp_result = loop.run_until_complete(mcp_client.search(company_name))
                
                # 検索が成功した場合
                if isinstance(mcp_result, dict) and mcp_result.get("success", False):
                    search_content = mcp_result.get("data", "")
                    search_process_log = mcp_result.get("process_log", [])
                    
                    # 画像の取得
                    logger.info(f"企業画像の検索を実行: {company_name}")
                    images_result = loop.run_until_complete(mcp_client.get_images(company_name))
                    
                    # 画像が成功した場合
                    if isinstance(images_result, dict) and images_result.get("success", False):
                        images_data = images_result.get("data", {})
                        images_process_log = images_result.get("process_log", [])
                        
                        # 結果を統合
                        combined_info = {}
                        
                        # 検索内容をJSONオブジェクトとしてパースを試みる
                        try:
                            search_data = json.loads(search_content)
                            if isinstance(search_data, dict):
                                content = search_data.get("content", "")
                                images_from_search = search_data.get("images", {})
                                
                                combined_info["content"] = content
                                combined_info["images"] = images_data if images_data else images_from_search
                            else:
                                combined_info["content"] = search_content
                                combined_info["images"] = images_data
                        except:
                            # JSONとして解析できない場合はテキストとして扱う
                            combined_info["content"] = search_content
                            combined_info["images"] = images_data
                        
                        # プロセスログを追加
                        combined_info["search_process_log"] = search_process_log
                        combined_info["images_process_log"] = images_process_log
                        
                        return {"success": True, "data": combined_info}
                    else:
                        # 画像検索に失敗した場合、検索結果のみを返す
                        search_data = {}
                        try:
                            search_data = json.loads(search_content)
                        except:
                            search_data = {"content": search_content}
                        
                        search_data["search_process_log"] = search_process_log
                        
                        return {"success": True, "data": search_data}
                else:
                    # 検索に失敗した場合はエラーを返す
                    error_message = mcp_result.get("error", "不明なエラー")
                    logger.error(f"MCP検索に失敗しました: {error_message}")
                    return {"error": error_message}
            finally:
                # イベントループを閉じる
                loop.close()
            
        except Exception as e:
            logger.error(f"詳細企業情報の取得中にエラーが発生しました: {str(e)}")
            return {"error": str(e)}