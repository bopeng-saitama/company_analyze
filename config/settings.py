"""設定管理モジュール"""

import os
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# 設定ファイルのパス
SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".company_analyzer_settings.json")

# デフォルト設定
DEFAULT_SETTINGS = {
    "tavily_api_key": "",
    "openai_api_key": "",
    "model_name": "gpt-4o-mini"
}

def get_settings() -> Dict[str, Any]:
    """
    設定を取得する
    
    Returns:
        現在の設定を含む辞書
    """
    settings = DEFAULT_SETTINGS.copy()
    
    try:
        # 環境変数から設定を読み込む
        if os.environ.get("TAVILY_API_KEY"):
            settings["tavily_api_key"] = os.environ.get("TAVILY_API_KEY")
        
        if os.environ.get("OPENAI_API_KEY"):
            settings["openai_api_key"] = os.environ.get("OPENAI_API_KEY")
        
        if os.environ.get("MODEL_NAME"):
            settings["model_name"] = os.environ.get("MODEL_NAME")
        
        # ファイルから設定を読み込む
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                file_settings = json.load(f)
                settings.update(file_settings)
        
        return settings
    
    except Exception as e:
        logger.error(f"設定の読み込みに失敗しました: {str(e)}")
        return DEFAULT_SETTINGS.copy()

def save_settings(settings: Dict[str, Any]) -> bool:
    """
    設定を保存する
    
    Args:
        settings: 保存する設定
        
    Returns:
        保存が成功したかどうか
    """
    try:
        # ディレクトリが存在しない場合は作成
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        
        # 設定をファイルに保存
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        
        logger.info("設定を保存しました")
        return True
    
    except Exception as e:
        logger.error(f"設定の保存に失敗しました: {str(e)}")
        return False

