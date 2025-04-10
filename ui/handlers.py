"""Gradio UIイベントハンドラの実装"""

from typing import Dict, Any, List, Tuple
import logging
import time
import tempfile
import os
import gradio as gr
import threading
import asyncio
import json
import datetime

from core.company_service import CompanyService
from core.report_service import ReportService
from core.api_service import ApiService
from ui.components import format_search_process

logger = logging.getLogger(__name__)

def handle_api_settings(tavily_key: str, openai_key: str) -> str:
    """
    API設定ハンドラ
    
    Args:
        tavily_key: Tavily API Key
        openai_key: OpenAI API Key
        
    Returns:
        ステータスメッセージ
    """
    if tavily_key == "●●●●●●●●":
        tavily_key = None
    
    if openai_key == "●●●●●●●●":
        openai_key = None
    
    result = ApiService.set_api_keys(tavily_key, openai_key)
    
    if result.get("success", False):
        # 成功メッセージのみを返す - ページリロードはappの方でハンドリング
        return "✅ APIキーを保存しました。"
    else:
        return f"❌ エラー: {result.get('message', '不明なエラー')}"

def handle_report_generation(
    company_name: str,
    search_depth: str,
    *section_values: bool,
    progress=gr.Progress()
) -> Tuple[str, str, Dict[str, Any], gr.update]:
    """
    レポート生成ハンドラ
    
    Args:
        company_name: 企業名またはURL
        search_depth: 検索深度
        *section_values: レポートセクションのチェックボックス値
        progress: Gradioプログレスコンポーネント
        
    Returns:
        レポート内容、ステータスメッセージ、検索プロセスデータ、検索プロセスアコーディオンの可視性
    """
    if not company_name:
        return "企業名を入力してください。", "エラー: 企業名が入力されていません。", None, gr.update(visible=False)
    
    # API状態の確認
    api_status = ApiService.get_api_status()
    if not api_status["tavily_key_set"] or not api_status["openai_key_set"]:
        return "APIキーが設定されていません。「API設定」タブからAPIキーを設定してください。", "エラー: APIキーが設定されていません。", None, gr.update(visible=False)
    
    # 検索深度の設定
    depth = "basic" if "基本" in search_depth else "advanced"
    
    # セクション設定の構築
    section_names = [
        "companyOverview", "management", "philosophy", "establishment",
        "businessDetails", "performance", "growth", "economicImpact",
        "competitiveness", "culture", "careerPath", "jobTypes",
        "workingConditions", "csrActivity", "relatedCompanies",
        "includeImages",  # 画像を含めるかどうかのオプション
        "showSearchProcess"  # 検索プロセスを表示するかどうかのオプション
    ]
    
    # 最後の2つの要素は画像を含めるかと検索プロセスを表示するかのフラグ
    include_images = section_values[-2]
    show_search_process = section_values[-1]
    
    # レポートセクションの辞書を作成
    report_sections = {}
    for i, name in enumerate(section_names[:-2]):  # 最後の2つ（画像と検索プロセス表示）を除く
        report_sections[name] = section_values[i]
    
    # プログレス表示の初期化
    progress(0, desc="初期化中...")
    status_message = "企業分析を開始します..."
    
    try:
        # 企業情報サービスの初期化
        progress(0.1, desc="企業情報サービスを初期化中...")
        company_service = CompanyService()
        
        # 企業情報の取得開始
        progress(0.2, desc=f"{company_name}の情報を検索中...")
        status_message = f"企業情報を取得中: {company_name}"
        
        # 企業情報の取得（セクション情報を渡す）
        company_result = company_service.get_company_info(company_name, depth, report_sections)
        
        if "error" in company_result:
            return f"企業情報の取得に失敗しました: {company_result['error']}", f"エラー: {company_result['error']}", None, gr.update(visible=False)
        
        company_info = company_result["data"]
        
        # 検索プロセスログの取得
        search_process_log = []
        if depth == "advanced" and isinstance(company_info, dict):
            # search_process_logが存在し、リストであることを確認
            if "search_process_log" in company_info and isinstance(company_info["search_process_log"], list):
                search_process_log = company_info["search_process_log"]
            
            # images_process_logが存在し、リストであることを確認
            if "images_process_log" in company_info and isinstance(company_info["images_process_log"], list):
                search_process_log.extend(company_info["images_process_log"])
        
        # 詳細調査の場合のプログレス表示調整
        if depth == "advanced":
            progress(0.4, desc="詳細な企業調査を実行中...")
            status_message += f"\n詳細な企業情報の調査を実行中..."
        
        progress(0.5, desc="企業情報の取得完了。レポート生成準備中...")
        status_message += f"\n企業情報を取得しました。レポートを生成中..."
        
        # 画像を含めない場合、画像データを削除
        if not include_images and isinstance(company_info, dict) and "images" in company_info:
            del company_info["images"]
        
        # レポート生成サービスの初期化
        report_service = ReportService()
        
        # レポート生成の開始
        progress(0.6, desc=f"{company_name}のレポートを生成中...")
        
        # レポート生成
        report_result = report_service.generate_report(company_name, company_info, report_sections)
        
        if "error" in report_result:
            return f"レポートの生成に失敗しました: {report_result['error']}", f"エラー: {report_result['error']}", None, gr.update(visible=False)
                
        # レポート生成完了
        progress(1.0, desc="レポート生成完了！")
        status_message += f"\nレポート生成が完了しました。"
        
        # 検索プロセスの表示設定
        search_process_accordion_visibility = gr.update(visible=show_search_process and depth == "advanced")
        
        return report_result["report"], status_message, search_process_log, search_process_accordion_visibility
    
    except Exception as e:
        logger.error(f"レポート生成中にエラーが発生しました: {str(e)}")
        return f"エラーが発生しました: {str(e)}", f"エラー: {str(e)}", None, gr.update(visible=False)

def save_markdown_for_download(report: str) -> str:
    """
    レポートをマークダウンファイルとして保存してダウンロード用に返す
    
    Args:
        report: マークダウン形式のレポート
        
    Returns:
        ダウンロード用ファイルのパス
    """
    if not report or report == "企業名を入力し、「レポート生成」ボタンをクリックしてください。":
        logger.error("ダウンロードするレポートがありません")
        return None
    
    try:
        # 企業名を抽出する試み
        company_name = "企業"
        if "# " in report:
            first_line = report.split("# ")[1].split("\n")[0] if len(report.split("# ")) > 1 else "企業"
            company_name = first_line.strip()
        
        # 企業名を含むファイル名（日本語ファイル名に対応）
        filename = f"{company_name}_分析レポート_{datetime.datetime.now().strftime('%Y%m%d')}.md"
        filename = filename.replace("/", "_").replace("\\", "_").replace(":", "_")  # ファイル名に使えない文字を置換
        
        # 一時ファイルを作成
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, filename)
        
        # ファイルを保存
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(report)
        
        logger.info(f"ダウンロード用ファイルを作成しました: {file_path}")
        return file_path
    
    except Exception as e:
        logger.error(f"ダウンロード用ファイル作成に失敗しました: {str(e)}")
        return None

def update_download_visibility(report: str) -> Dict[str, Any]:
    """
    レポートの内容に基づいてダウンロードボタンの表示状態を更新する
    
    Args:
        report: マークダウン形式のレポート
        
    Returns:
        ダウンロードボタンの表示状態を表す辞書
    """
    if report and "企業名を入力" not in report:
        return gr.update(visible=True)
    else:
        return gr.update(visible=False)