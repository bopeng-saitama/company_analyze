"""企業情報を取得するサービス"""

from typing import Dict, Any, Optional
import logging
import json

from tavily import TavilyClient

from config.settings import get_settings

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
            
            # 企業名またはURLから検索クエリを構築
            query = company_name
            if not (query.startswith('http://') or query.startswith('https://')):
                query = f"{query} 企業情報 会社概要"
            
            logger.info(f"検索クエリ: {query}")
            
            # Tavilyで企業情報を取得
            logger.info("Tavily APIを呼び出し中...")
            company_info = self.client.get_company_info(
                query=query,
                search_depth=search_depth
            )
            
            # 取得した情報をログに記録（機密情報が含まれないよう注意）
            try:
                info_preview = str(company_info)[:500] + "..." if len(str(company_info)) > 500 else str(company_info)
                logger.info(f"取得した企業情報プレビュー: {info_preview}")
            except:
                logger.info("企業情報のプレビューを表示できません")
            
            logger.info(f"企業情報の取得完了: {company_name}")
            return {"success": True, "data": company_info}
        
        except Exception as e:
            logger.error(f"企業情報の取得中にエラーが発生しました: {str(e)}")
            return {"error": str(e)}