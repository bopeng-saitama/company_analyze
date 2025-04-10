"""Gradioアプリケーションの定義"""

import gradio as gr
from typing import Dict, Any, Tuple, List
import logging
import json

from ui.components import create_api_settings_ui, create_report_ui
from ui.handlers import handle_api_settings, handle_report_generation, save_markdown_for_download, update_download_visibility
from core.api_service import ApiService

logger = logging.getLogger(__name__)

def create_gradio_app() -> gr.Blocks:
    """
    Gradioアプリケーションを作成する
    
    Returns:
        Gradioアプリケーション
    """
    # アプリケーションの初期化
    with gr.Blocks(
        title="企業分析レポート生成ツール",
        theme=gr.themes.Soft(),
        css="""
        .footer {
            text-align: center;
            margin-top: 20px;
            color: #666;
        }
        .api-status {
            margin-top: 10px;
            padding-top: 10px;
            border-top: 1px solid #eee;
        }
        .search-process {
            font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            padding: 10px;
            background-color: #f8f9fa;
            border-radius: 8px;
            margin-bottom: 10px;
        }
        .process-step {
            margin-bottom: 15px;
            padding: 10px;
            border-left: 3px solid #4CAF50;
            background-color: #fff;
            border-radius: 4px;
        }
        .process-step h4 {
            margin-top: 0;
            margin-bottom: 8px;
            color: #2E7D32;
        }
        .error {
            color: #D32F2F;
            font-weight: bold;
        }
        details summary {
            cursor: pointer;
            padding: 5px;
            background-color: #f1f1f1;
            border-radius: 4px;
        }
        details[open] summary {
            margin-bottom: 8px;
        }
        """
    ) as app:
        gr.Markdown("# 企業分析レポート生成ツール")
        
        # API状態の取得
        api_status = ApiService.get_api_status()
        
        # タブの作成
        with gr.Tabs() as tabs:
            with gr.TabItem("レポート生成"):
                # レポート生成UI
                company_input, search_depth, section_checkboxes, generate_btn, report_output, status_output, download_btn, file_output, search_process_accordion, search_process_json = create_report_ui()
                
                # APIステータス表示
                with gr.Row():
                    with gr.Column():
                        api_status_md = gr.Markdown(
                            f"""
                            <div class="api-status">
                            <p>Tavily API: {'✅ 設定済み' if api_status['tavily_key_set'] else '❌ 未設定'}</p>
                            <p>OpenAI API: {'✅ 設定済み' if api_status['openai_key_set'] else '❌ 未設定'}</p>
                            </div>
                            """,
                            elem_id="api_status"
                        )
                
                # レポート生成ボタンのイベントハンドラ
                generate_result = generate_btn.click(
                    fn=handle_report_generation,
                    inputs=[company_input, search_depth] + section_checkboxes,
                    outputs=[report_output, status_output, search_process_json, search_process_accordion],
                    show_progress=True  # プログレスバーを表示
                )
                
                # レポート生成後にダウンロードボタンを表示
                generate_result.then(
                    fn=update_download_visibility,
                    inputs=[report_output],
                    outputs=[download_btn]
                )
                
                # ダウンロードボタンのイベントハンドラ
                download_btn.click(
                    fn=save_markdown_for_download,
                    inputs=[report_output],  # レポート内容を入力として渡す
                    outputs=[file_output]
                )
            
            with gr.TabItem("API設定"):
                # API設定UI
                tavily_key, openai_key, save_btn, settings_status = create_api_settings_ui(
                    tavily_key_set=api_status['tavily_key_set'],
                    openai_key_set=api_status['openai_key_set']
                )
                
                # 説明テキストの追加
                gr.Markdown("""
                ### 注意事項
                - APIキーを設定すると、ここで保存されます
                - 設定後は、ページを再読み込みするとステータスが更新されます
                """)
                
                # 設定保存ボタンのイベントハンドラ
                save_result = save_btn.click(
                    fn=handle_api_settings,
                    inputs=[tavily_key, openai_key],
                    outputs=[settings_status]
                )
                
                # 保存成功時にページリロードを促すJavaスクリプトを追加
                save_result.then(
                    fn=lambda: gr.update(value="✅ APIキーを保存しました。<br>3秒後にページを再読み込みします...<script>setTimeout(function() { window.location.reload(); }, 3000);</script>"),
                    inputs=None,
                    outputs=[settings_status]
                )
            
            with gr.TabItem("ヘルプ"):
                gr.Markdown("""
                ## 企業分析レポート生成ツールの使い方
                
                このツールは企業に関する情報を収集し、詳細な分析レポートを自動生成します。
                
                ### 基本的な使い方
                
                1. 「API設定」タブで、必要なAPIキーを設定します。
                2. 「レポート生成」タブで分析したい企業名を入力します。
                3. 検索深度を選択します:
                   - 基本分析: 短時間で基本的な情報を収集します
                   - 詳細分析: より詳細な情報を収集しますが、時間がかかります
                4. 含めたいレポートの項目にチェックを入れます
                5. 「レポート生成」ボタンをクリックして分析を開始します
                6. 分析結果が表示されたら「レポートをダウンロード」ボタンでレポートを保存できます
                
                ### 詳細モードの機能
                
                詳細モードでは以下の機能が利用できます：
                
                - **詳細な情報収集**: より多くのソースから情報を収集します
                - **画像の取得**: 企業に関連する画像を取得してレポートに含めます
                - **検索プロセスの表示**: AIがどのように情報を収集・分析したかを確認できます
                
                ### ヒント
                
                - 正確な企業名を入力すると、より精度の高い結果が得られます
                - 会社名だけでなく、「株式会社」なども含めるとより正確な結果が得られます
                - 日本語の会社名だけでなく、英語の社名や証券コードでも検索できます
                
                ### ダウンロードに関する注意
                
                - ダウンロードボタンをクリックすると、マークダウン形式のレポートがダウンロードされます
                - ブラウザによっては、ダウンロードを許可する必要があるかもしれません
                - ダウンロードしたファイルは拡張子が `.md` のマークダウンファイルです
                """)
        
        # フッター
        gr.Markdown(
            """
            <div class="footer">
            © 2025 企業分析レポート生成ツール | Powered by Tavily & OpenAI
            </div>
            """
        )
    
    return app