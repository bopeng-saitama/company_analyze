"""フォーマット処理ユーティリティ"""

import re
from typing import Dict, Any

def format_report(report: str) -> str:
    """
    生成されたレポートを整形する
    
    Args:
        report: 生成されたレポート
        
    Returns:
        整形されたレポート
    """
    # 見出しの前に空行を追加
    report = re.sub(r'(\n#{1,6}\s)', r'\n\1', report)
    
    # 見出しの後に空行を追加
    report = re.sub(r'(#{1,6}\s.+)(\n(?!#|\n))', r'\1\n\2', report)
    
    # 連続する空行を1つにまとめる
    report = re.sub(r'\n{3,}', r'\n\n', report)
    
    return report