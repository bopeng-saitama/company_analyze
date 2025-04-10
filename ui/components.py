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

def create_report_ui() -> Tuple[gr.Textbox, gr.Dropdown, List[gr.Checkbox], gr.Button, gr.Markdown, gr.Textbox, gr.Button, gr.File]:
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
                    value="基本分析 (速度優先)"
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
                    working_conditions, csr_activity, related_companies
                ]
                
                generate_btn = gr.Button("レポート生成", variant="primary")
                
            # 右側カラム (レポート表示)
            with gr.Column(scale=2):
                report_output = gr.Markdown(
                    "企業名を入力し、「レポート生成」ボタンをクリックしてください。",
                    label="分析レポート"
                )
                
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
        
        return company_input, search_depth, section_checkboxes, generate_btn, report_output, status_output, download_btn, file_output

def create_progress_updater(progress_component):
    """
    プログレス更新関数を作成
    
    Args:
        progress_component: Gradioのプログレスコンポーネント
        
    Returns:
        更新関数
    """
    def update_progress(percentage, text=None):
        progress_component.update(value=percentage/100)
        if text:
            return gr.update(value=f"{text} ({percentage:.0f}%)")
        return None
    
    return update_progress