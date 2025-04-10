"""Gradio UIコンポーネントの定義"""

import gradio as gr
from typing import Dict, Any, Tuple, List

def create_api_settings_ui(tavily_key_set: bool, openai_key_set: bool) -> Tuple[gr.Textbox, gr.Textbox, gr.Button, gr.Markdown]:
    """
    API設定用UIコンポーネントを作成する
    
    Args:
        tavily_key_set: TavilyのAPIキーが設定されているかどうか
        openai_key_set: OpenAIのAPIキーが設定されているかどうか
        
    Returns:
        API設定用UIコンポーネント
    """
    with gr.Column():
        gr.Markdown("## API設定")
        gr.Markdown("企業分析を行うには、TavilyとOpenAIのAPIキーが必要です。")
        
        with gr.Row():
            tavily_key = gr.Textbox(
                label="Tavily API キー", 
                placeholder="Tavily API キーを入力", 
                type="password",
                value="●●●●●●●●" if tavily_key_set else ""
            )
        
        with gr.Row():
            openai_key = gr.Textbox(
                label="OpenAI API キー", 
                placeholder="OpenAI API キーを入力", 
                type="password",
                value="●●●●●●●●" if openai_key_set else ""
            )
        
        save_btn = gr.Button("設定を保存", variant="primary")
        settings_status = gr.Markdown("")
        
        return tavily_key, openai_key, save_btn, settings_status

def create_search_process_ui() -> Tuple[gr.Accordion, gr.JSON]:
    """
    検索プロセスを表示するためのUIコンポーネントを作成する
    
    Returns:
        検索プロセス表示用UIコンポーネント
    """
    with gr.Accordion("検索プロセスの詳細", open=False) as search_process_accordion:
        gr.Markdown("""
        <div style="margin-bottom: 10px;">
            検索プロセスの詳細を確認できます。検索クエリの生成、ウェブページの取得、情報の抽出など、各ステップの詳細が表示されます。
        </div>
        """)
        search_process_json = gr.JSON(
            label="検索プロセスデータ",
            visible=True
        )
    
    return search_process_accordion, search_process_json

def create_report_ui() -> Tuple[gr.Textbox, gr.Dropdown, List[gr.Checkbox], gr.Button, gr.Markdown, gr.Textbox, gr.Button, gr.File, gr.Accordion, gr.JSON]:
    """
    レポート生成用UIコンポーネントを作成する
    
    Returns:
        レポート生成用UIコンポーネント
    """
    with gr.Column():
        with gr.Row():
            # 左側カラム (入力コントロール)
            with gr.Column(scale=1):
                company_input = gr.Textbox(
                    label="企業名またはウェブサイト", 
                    placeholder="例: トヨタ自動車 または toyota.co.jp",
                    lines=1
                )
                
                search_depth = gr.Dropdown(
                    ["基本分析 (速度優先)", "詳細分析 (精度優先)"],
                    label="検索深度",
                    value="基本分析 (速度優先)",
                    info="詳細分析では、より多くの情報源から包括的な調査を行い、画像も取得します。"
                )
                
                # 新しいオプション
                gr.Markdown("### 詳細分析オプション")
                with gr.Row():
                    include_images = gr.Checkbox(
                        label="画像を含める", 
                        value=True,
                        interactive=True,
                        info="企業に関連する画像をレポートに含めます。"
                    )
                    
                    show_search_process = gr.Checkbox(
                        label="検索プロセスを表示",
                        value=True,
                        interactive=True,
                        info="検索の詳細なプロセスを表示します。"
                    )
                
                gr.Markdown("### レポート項目")
                
                with gr.Row():
                    with gr.Column(scale=1):
                        company_overview = gr.Checkbox(label="企業概要", value=True)
                        management = gr.Checkbox(label="代表取締役", value=True)
                        philosophy = gr.Checkbox(label="企業理念", value=True)
                        establishment = gr.Checkbox(label="設立・資本金", value=True)
                        business_details = gr.Checkbox(label="事業内容", value=True)
                        performance = gr.Checkbox(label="業績", value=True)
                        growth = gr.Checkbox(label="成長性", value=True)
                        economic_impact = gr.Checkbox(label="景況影響度", value=True)
                    
                    with gr.Column(scale=1):
                        competitiveness = gr.Checkbox(label="競争力", value=True)
                        culture = gr.Checkbox(label="社風", value=True)
                        career_path = gr.Checkbox(label="キャリア形成", value=True)
                        job_types = gr.Checkbox(label="職種", value=True)
                        working_conditions = gr.Checkbox(label="勤務条件", value=True)
                        csr_activity = gr.Checkbox(label="CSR活動", value=True)
                        related_companies = gr.Checkbox(label="関連企業", value=True)
                
                section_checkboxes = [
                    company_overview, management, philosophy, establishment,
                    business_details, performance, growth, economic_impact,
                    competitiveness, culture, career_path, job_types,
                    working_conditions, csr_activity, related_companies,
                    include_images,  # 画像を含めるオプション
                    show_search_process  # 検索プロセスを表示するオプション
                ]
                
                generate_btn = gr.Button("レポート生成", variant="primary")
                
            # 右側カラム (レポート表示)
            with gr.Column(scale=2):
                report_output = gr.Markdown(
                    "企業名を入力し、「レポート生成」ボタンをクリックしてください。",
                    label="分析レポート"
                )
                
                # 検索プロセス表示コンポーネント
                search_process_accordion, search_process_json = create_search_process_ui()
                
                # 処理状況表示
                status_output = gr.Textbox(
                    label="処理状況",
                    lines=3,
                    interactive=False
                )
                
                with gr.Row():
                    download_btn = gr.Button(
                        "レポートをダウンロード", 
                        variant="secondary",
                        visible=False
                    )
                    
                    # ダウンロードファイルの出力コンポーネント
                    file_output = gr.File(
                        label="ダウンロード", 
                        interactive=False, 
                        visible=False
                    )
        
        # 検索深度が変更されたときのイベントハンドラを定義
        def update_image_options(depth):
            if depth == "基本分析 (速度優先)":
                return [
                    gr.update(value=False, interactive=False),  # include_images
                    gr.update(value=False, interactive=False)   # show_search_process
                ]
            else:
                return [
                    gr.update(value=True, interactive=True),  # include_images
                    gr.update(value=True, interactive=True)   # show_search_process
                ]
        
        search_depth.change(
            fn=update_image_options,
            inputs=[search_depth],
            outputs=[include_images, show_search_process]
        )
        
        return company_input, search_depth, section_checkboxes, generate_btn, report_output, status_output, download_btn, file_output, search_process_accordion, search_process_json

def format_search_process(process_log: List[Dict[str, Any]]) -> str:
    """
    検索プロセスログをHTMLフォーマットに変換する
    
    Args:
        process_log: 検索プロセスログ
        
    Returns:
        HTML形式のプロセスログ
    """
    if not process_log:
        return "<p>検索プロセスのログがありません。</p>"
    
    html = "<div class='search-process'>"
    
    for step in process_log:
        step_name = step.get("step", "不明なステップ")
        html += f"<div class='process-step'><h4>{step_name}</h4>"
        
        # ステップに応じた情報の表示
        if step_name == "検索開始":
            html += f"<p>ユーザークエリ: {step.get('user_query', '不明')}</p>"
            html += "<p>初期検索クエリ:</p><ul>"
            for query in step.get("initial_search_queries", []):
                html += f"<li>{query}</li>"
            html += "</ul>"
        
        elif step_name == "ウェブ検索":
            html += f"<p>検索クエリ: {step.get('query', '不明')}</p>"
            html += "<p>検索結果:</p><ul>"
            for result in step.get("results", []):
                html += f"<li><a href='{result.get('url', '#')}' target='_blank'>{result.get('title', 'タイトルなし')}</a></li>"
            html += "</ul>"
        
        elif step_name == "有用性評価":
            html += f"<p>評価結果: {step.get('evaluation', '不明')}</p>"
            html += f"<p>コンテンツプレビュー: {step.get('url_content_preview', '内容なし')}</p>"
        
        elif step_name == "情報抽出":
            html += f"<p>クエリ: {step.get('query', '不明')}</p>"
            html += f"<p>検索クエリ: {step.get('search_query', '不明')}</p>"
            html += f"<details><summary>抽出されたコンテンツ</summary><p>{step.get('extracted_content', '内容なし')}</p></details>"
        
        elif step_name == "次の検索クエリ決定":
            html += "<p>判断結果: " + (step.get('decision', '不明')) + "</p>"
        
        elif step_name == "画像検索開始":
            html += f"<p>クエリ: {step.get('query', '不明')}</p>"
        
        elif step_name == "画像説明生成":
            html += f"<p>画像URL: <a href='{step.get('image_url', '#')}' target='_blank'>{step.get('image_url', 'リンク')}</a></p>"
            html += f"<p>説明: {step.get('description', '説明なし')}</p>"
        
        elif "エラー" in step_name:
            html += f"<p class='error'>エラー内容: {step.get('error', '不明なエラー')}</p>"
        
        html += "</div>"
    
    html += "</div>"
    return html

def create_progress_updater(progress_component):
    """
    プログレス更新関数を作成
    
    Args:
        progress_component: Gradioのプログレスコンポーネント
        
    Returns:
        更新関数
    """
    def update_progress(percentage, text=None):
        progress_component.update(value=percentage)
        if text:
            return gr.update(value=f"{text} ({percentage*100:.0f}%)")
        return None
    
    return update_progress