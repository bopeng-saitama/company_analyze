"""Gradio UIイベントハンドラの実装"""

from typing import Dict, Any, List, Tuple
import logging
import time
import tempfile
import os
import gradio as gr
import threading

from core.company_service import CompanyService
from core.report_service import ReportService
from core.api_service import ApiService

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
) -> Tuple[str, str]:
    """
    レポート生成ハンドラ
    
    Args:
        company_name: 企業名またはURL
        search_depth: 検索深度
        *section_values: レポートセクションのチェックボックス値
        progress: Gradioプログレスコンポーネント
        
    Returns:
        レポート内容とステータスメッセージ
    """
    if not company_name:
        return "企業名を入力してください。", "エラー: 企業名が入力されていません。"
    
    # API状態の確認
    api_status = ApiService.get_api_status()
    if not api_status["tavily_key_set"] or not api_status["openai_key_set"]:
        return "APIキーが設定されていません。「API設定」タブからAPIキーを設定してください。", "エラー: APIキーが設定されていません。"
    
    # 検索深度の設定
    depth = "basic" if "基本" in search_depth else "advanced"
    
    # セクション設定の構築
    section_names = [
        "companyOverview", "management", "philosophy", "establishment",
        "businessDetails", "performance", "growth", "economicImpact",
        "competitiveness", "culture", "careerPath", "jobTypes",
        "workingConditions", "csrActivity", "relatedCompanies"
    ]
    
    report_sections = dict(zip(section_names, section_values))
    
    # プログレス表示の初期化
    progress(0, desc="初期化中...")
    status_message = "企業分析を開始します..."
    
    try:
        # 企業情報サービスの初期化
        progress(10, desc="企業情報サービスを初期化中...")
        company_service = CompanyService()
        
        # 企業情報の取得開始
        progress(20, desc=f"{company_name}の情報を検索中...")
        status_message = f"企業情報を取得中: {company_name}"
        
        # 企業情報の取得
        company_result = company_service.get_company_info(company_name, depth)
        
        if "error" in company_result:
            return f"企業情報の取得に失敗しました: {company_result['error']}", f"エラー: {company_result['error']}"
        
        company_info = company_result["data"]
        progress(50, desc="企業情報の取得完了。レポート生成準備中...")
        status_message += f"\n企業情報を取得しました。レポートを生成中..."
        
        # レポート生成サービスの初期化
        report_service = ReportService()
        
        # レポート生成の開始
        progress(60, desc=f"{company_name}のレポートを生成中...")
        
        # レポート生成
        report_result = report_service.generate_report(company_name, company_info, report_sections)
        
        if "error" in report_result:
            return f"レポートの生成に失敗しました: {report_result['error']}", f"エラー: {report_result['error']}"
        
        # レポート生成完了
        progress(100, desc="レポート生成完了！")
        status_message += f"\nレポート生成が完了しました。"
        
        return report_result["report"], status_message
    
    except Exception as e:
        logger.error(f"レポート生成中にエラーが発生しました: {str(e)}")
        return f"エラーが発生しました: {str(e)}", f"エラー: {str(e)}"

def save_markdown_for_download(report: str) -> str:
    """
    レポートをマークダウンファイルとして保存してダウンロード用に返す
    
    Args:
        report: マークダウン形式のレポート
        
    Returns:
        ダウンロード用ファイルのパス
    """
    if not report or report == "企業名を入力し、「レポート生成」ボタンをクリックしてください。":
        return None
    
    try:
        # 一時ファイルを作成
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, "企業分析レポート.md")
        
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