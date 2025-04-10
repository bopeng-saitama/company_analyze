"""ファイル操作ユーティリティ"""

import os
import logging
import tempfile
from typing import Dict, Any, Optional
import base64

logger = logging.getLogger(__name__)

def save_markdown_file(content: str, file_path: Optional[str] = None) -> Dict[str, Any]:
    """
    マークダウンファイルを保存する
    
    Args:
        content: ファイルの内容
        file_path: 保存先のファイルパス（指定しない場合はデフォルトの場所）
        
    Returns:
        保存結果を含む辞書
    """
    try:
        if not file_path:
            # デフォルトのファイル名を設定
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            file_path = os.path.join(desktop, "企業分析レポート.md")
        
        # ファイルを保存
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"ファイルを保存しました: {file_path}")
        return {
            "success": True,
            "path": file_path
        }
    
    except Exception as e:
        logger.error(f"ファイルの保存に失敗しました: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def get_file_as_base64(file_path: str) -> Optional[str]:
    """
    ファイルをBase64エンコードした文字列として取得する
    
    Args:
        file_path: ファイルパス
        
    Returns:
        Base64エンコードされた文字列、またはNone（エラー時）
    """
    try:
        with open(file_path, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')
    
    except Exception as e:
        logger.error(f"ファイルの読み込みに失敗しました: {str(e)}")
        return None

def create_downloadable_markdown(content: str) -> str:
    """
    ダウンロード可能なマークダウンファイルを作成して、そのパスを返す
    
    Args:
        content: ファイルの内容
        
    Returns:
        一時ファイルのパス
    """
    try:
        # 一時ファイルを作成
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, "企業分析レポート.md")
        
        # ファイルを保存
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"ダウンロード用ファイルを作成しました: {file_path}")
        return file_path
    
    except Exception as e:
        logger.error(f"ダウンロード用ファイル作成に失敗しました: {str(e)}")
        return None