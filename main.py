"""企業分析ツールのエントリーポイント"""

import logging
import os
import sys

from config.logging_config import setup_logging
from ui.app import create_gradio_app

# ロギングの設定
setup_logging()
logger = logging.getLogger(__name__)

def main():
    """アプリケーションのメインエントリーポイント"""
    try:
        logger.info("企業分析ツールを起動しています...")
        
        # Gradioアプリの作成と起動
        app = create_gradio_app()
        
        # アプリケーションの起動
        app.launch(
            server_name="127.0.0.1",     # すべてのネットワークインターフェイスでリッスン
            server_port=7860,          # デフォルトのGradioポート
            share=False,               # 公開リンクは不要
            inbrowser=True             # ブラウザを自動で開く
            # favicon_path パラメータを削除
        )
        
    except Exception as e:
        logger.error(f"アプリケーションの起動に失敗しました: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()