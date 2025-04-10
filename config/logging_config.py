"""ロギング設定モジュール"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler

# ログファイルのパス
LOG_DIRECTORY = os.path.join(os.path.expanduser("~"), ".company_analyzer")
LOG_FILE = os.path.join(LOG_DIRECTORY, "company_analyzer.log")

def setup_logging():
    """ロギングを設定する"""
    try:
        # ログディレクトリが存在しない場合は作成
        os.makedirs(LOG_DIRECTORY, exist_ok=True)
        
        # ルートロガーの設定
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        
        # フォーマッター
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        # ファイルハンドラ (ローテーション付き)
        file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=1024 * 1024 * 5,  # 5 MB
            backupCount=3,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        
        # コンソールハンドラ
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        
        # ハンドラーの追加
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)
        
        # ログ開始メッセージ
        logging.info("ロギングを初期化しました")
        
    except Exception as e:
        print(f"ロギングの設定に失敗しました: {str(e)}")
        # エラーが発生した場合は基本的なコンソールログだけを設定
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

