"""API設定を管理するサービス"""

from typing import Dict, Any, Optional
import logging
import json
import os

from config.settings import get_settings, save_settings

logger = logging.getLogger(__name__)

class ApiService:
    """API設定を管理するサービスクラス"""
    
    @staticmethod
    def set_api_keys(tavily_api_key: Optional[str] = None, openai_api_key: Optional[str] = None) -> Dict[str, Any]:
        """
        API Keyを設定する
        
        Args:
            tavily_api_key: Tavily API Key
            openai_api_key: OpenAI API Key
            
        Returns:
            設定結果を含む辞書
        """
        settings = get_settings()
        
        try:
            # 既存の設定を読み込み
            if tavily_api_key:
                settings["tavily_api_key"] = tavily_api_key
            
            if openai_api_key:
                settings["openai_api_key"] = openai_api_key
            
            # 設定を保存
            save_settings(settings)
            
            logger.info("API設定を保存しました")
            return {
                "success": True,
                "message": "API設定を保存しました"
            }
        
        except Exception as e:
            logger.error(f"API設定の保存中にエラーが発生しました: {str(e)}")
            return {
                "error": str(e),
                "message": "API設定の保存に失敗しました"
            }
    
    @staticmethod
    def get_api_status() -> Dict[str, Any]:
        """
        API設定の状態を取得する
        
        Returns:
            API設定の状態を含む辞書
        """
        settings = get_settings()
        
        return {
            "tavily_key_set": bool(settings.get("tavily_api_key")),
            "openai_key_set": bool(settings.get("openai_api_key"))
        }