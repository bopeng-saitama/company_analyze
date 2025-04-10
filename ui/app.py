"""Gradioアプリケーションの定義"""

import gradio as gr
from typing import Dict, Any, Tuple, List
import logging

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
        """
    ) as app:
        gr.Markdown("# 企業分析レポート生成ツール")
        
        # API状態の取得
        api_status = ApiService.get_api_status()
        
        # タブの作成
        with gr.Tabs() as tabs:
            with gr.TabItem("レポート生成"):
                # レポート生成UI
                company_input, search_depth, section_checkboxes, generate_btn, report_output, status_output, download_btn, file_output = create_report_ui()
                
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
                    outputs=[report_output, status_output],
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
                    inputs=[report_output],
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
                
                # 保存成功時にページリロードを促すJavaScriptを追加
                save_result.then(
                    fn=lambda: gr.update(value="✅ APIキーを保存しました。<br>3秒後にページを再読み込みします...<script>setTimeout(function() { window.location.reload(); }, 3000);</script>"),
                    inputs=None,
                    outputs=[settings_status]
                )
        
        # フッター
        gr.Markdown(
            """
            <div class="footer">
            © 2025 企業分析レポート生成ツール | Powered by Tavily & OpenAI
            </div>
            """
        )
    
    return app