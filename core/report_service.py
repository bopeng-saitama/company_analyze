"""企業分析レポートを生成するサービス"""

from typing import Dict, Any, Optional, List
import logging
import json
from openai import OpenAI
import re

from config.settings import get_settings
from utils.format_utils import format_report

logger = logging.getLogger(__name__)

class ReportService:
    """企業分析レポートを生成するためのサービスクラス"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        ReportServiceの初期化
        
        Args:
            api_key: OpenAI API Key。指定されない場合は設定から読み込む
        """
        settings = get_settings()
        self.api_key = api_key or settings.get("openai_api_key", "")
        self.model_name = settings.get("model_name", "chatgpt-4o-latest")
        self.client = None
        
        if self.api_key:
            self.init_client()
    
    def init_client(self) -> bool:
        """OpenAIクライアントを初期化する"""
        try:
            self.client = OpenAI(api_key=self.api_key)
            logger.info("OpenAIクライアントを初期化しました")
            return True
        except Exception as e:
            logger.error(f"OpenAIクライアントの初期化に失敗しました: {e}")
            return False
    
    def _format_image_data(self, images_data: Any) -> str:
        """
        画像データを適切なマークダウン形式に整形する
        
        Args:
            images_data: 画像データ
            
        Returns:
            マークダウン形式の画像情報
        """
        if not images_data:
            return ""
            
        images_markdown = ""
        
        try:
            if isinstance(images_data, dict):
                # エラーメッセージや「画像なし」メッセージがある場合
                if "error" in images_data:
                    return f"*注: {images_data['error']}*\n\n"
                    
                if "no_images" in images_data:
                    return f"*注: {images_data['no_images']}*\n\n"
                
                # 新しい画像データ形式 (image_0, image_1など)の処理
                for key, value in images_data.items():
                    if key.startswith("image_") and isinstance(value, dict):
                        if "url" in value and "description" in value:
                            images_markdown += f"- ![{value['description']}]({value['url']}) - {value['description']}\n"
                
                # 旧形式の画像データ処理 (URL -> 説明のマッピング)
                for url, description in images_data.items():
                    if url != "no_images" and "error" not in url and not url.startswith("process_log") and isinstance(description, str):
                        images_markdown += f"- ![{description}]({url}) - {description}\n"
            
            # リストの場合の処理（念のため）
            elif isinstance(images_data, list):
                for item in images_data:
                    if isinstance(item, dict) and "url" in item and "description" in item:
                        images_markdown += f"- ![{item['description']}]({item['url']}) - {item['description']}\n"
        
        except Exception as e:
            logger.error(f"画像データの整形中にエラーが発生しました: {str(e)}")
            return "注: 画像データの処理中にエラーが発生しました。\n\n"
            
        return images_markdown

    def _generate_missing_info(self, company_name: str, missing_sections: List[str]) -> str:
        """
        不足している情報を生成する
        
        Args:
            company_name: 企業名
            missing_sections: 不足しているセクション
            
        Returns:
            生成された情報
        """
        if not missing_sections:
            return ""
        
        prompt = f"""あなたは企業分析のエキスパートです。{company_name}に関する以下の情報が不足しています。
        
        不足しているセクション: {', '.join(missing_sections)}
        
        公開されている一般的な情報や、同業他社の標準的な情報を基に、それぞれのセクションについて可能な限り妥当な情報を提供してください。
        各セクションには必ず何らかの内容を提供し、「情報なし」や「不明」といった表現は避けてください。
        
        回答は以下の形式でお願いします:
        
        ## [セクション名]
        [妥当な内容]
        
        ## [セクション名]
        [妥当な内容]
        
        ...
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "あなたは企業分析のエキスパートです。不足している情報を提供します。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7  # 少し創造性を上げる
            )
            
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"不足情報の生成中にエラーが発生しました: {str(e)}")
            return ""
    
    def generate_report(
        self, 
        company_name: str, 
        company_info: Dict[str, Any], 
        report_sections: Dict[str, bool]
    ) -> Dict[str, Any]:
        """
        企業分析レポートを生成する
        
        Args:
            company_name: 企業名
            company_info: 企業情報
            report_sections: レポートに含めるセクション
            
        Returns:
            生成されたレポートを含む辞書
        """
        if not self.client:
            logger.error("OpenAIクライアントが初期化されていません")
            return {"error": "API キーが設定されていません"}
        
        try:
            # 選択されたセクションをログに記録
            selected_sections = [name for name, include in report_sections.items() if include]
            logger.info(f"選択されたレポートセクション: {', '.join(selected_sections)}")
            
            # レポートに含めるセクションを定義
            sections_description = """
企業分析レポートには以下のセクションが含まれます：
- 企業概要：企業の規模、歴史、主要事業について
- 代表取締役：氏名、経歴、代表メッセージ
- 企業理念：創業以来の理念・精神
- 設立年・資本金・株式公開・事業拠点：企業の基本情報
- 事業内容：商品・サービスの詳細、対象者、業態
- 業績：売上高、営業利益（率）
- 成長性：売上高・営業利益の伸び率、新規事業・事業拡大の展望
- 景況・経済動向による影響度：経済状況による業績変化
- 競争力：商品・サービスの開発力・技術力・品質、競合他社との比較
- 社風：年齢・男女別の人員構成、意思決定の仕組み、職場の雰囲気
- キャリア形成の環境：昇給・昇進の仕組み、平均勤続年数、役職者の平均年齢
- 職種：職種の種類、求められるスキル
- 勤務条件：給与、勤務地、勤務時間、休日、手当、福利厚生、保険
- CSR活動・ダイバーシティーの取り組み：社会的責任や多様性の取り組み
- 関連企業：親会社・子会社、グループ会社、資本提携会社・業務提携会社
"""

            # 含めるセクションを整形
            included_sections = []
            section_mapping = {
                "companyOverview": "企業概要",
                "management": "代表取締役",
                "philosophy": "企業理念",
                "establishment": "設立年・資本金・株式公開・事業拠点",
                "businessDetails": "事業内容",
                "performance": "業績",
                "growth": "成長性",
                "economicImpact": "景況・経済動向による影響度",
                "competitiveness": "競争力",
                "culture": "社風",
                "careerPath": "キャリア形成の環境",
                "jobTypes": "職種",
                "workingConditions": "勤務条件",
                "csrActivity": "CSR活動・ダイバーシティーの取り組み",
                "relatedCompanies": "関連企業"
            }
            
            for section, included in report_sections.items():
                if included:
                    included_sections.append(section)
            
            # 企業情報から詳細な研究データと画像データを抽出
            detailed_research = ""
            images_markdown = ""
            
            # company_infoがない場合やNoneの場合は空の辞書を使用
            if not company_info:
                company_info = {}
            
            # 詳細研究データの取得
            if isinstance(company_info, dict) and "detailed_research" in company_info:
                detailed_research = company_info.get("detailed_research", "")
            
            # 画像データの取得と整形
            if isinstance(company_info, dict) and "images" in company_info:
                images_data = company_info.get("images", {})
                images_markdown = self._format_image_data(images_data)
            
            # 基本企業情報からdetailed_research、images、process_logを除去（プロンプトを短くするため）
            company_info_basic = {}
            if isinstance(company_info, dict):
                company_info_basic = {k: v for k, v in company_info.items() 
                                    if k not in ["detailed_research", "images", "search_process_log", "images_process_log"]}
            
            # プロンプト作成
            prompt = f"""あなたは企業分析のエキスパートです。与えられた情報をもとに、{company_name}の企業分析レポートを作成してください。

企業に関する基本情報：
<企業情報>
{json.dumps(company_info_basic, ensure_ascii=False, indent=2)}
</企業情報>

詳細な調査情報：
<詳細調査>
{detailed_research}
</詳細調査>

企業の画像情報：
<画像情報>
{images_markdown}
</画像情報>

{sections_description}

次のセクションを含めてレポートを作成してください：{", ".join([section_mapping.get(s, s) for s in included_sections])}

以下の点に注意してください：
1. 各セクションには必ず内容を記載し、「情報なし」という記載は絶対に避けてください。
2. 情報が不足している場合は、公開されている一般的な情報や同業他社の標準的な情報を基に、妥当な情報を推測して提供してください。
3. 必ず日本語で出力してください。
4. 指定したセクションに関する情報を優先的に含めてください。
5. データに基づく具体的な分析を含めてください。
6. 詳細な調査情報があれば、それを活用してください。
7. 画像情報がある場合は、適切な場所にマークダウン形式で画像を挿入してください。
8. レポートはマークダウン形式で作成してください。
9. 代表取締役、設立年、資本金などの基本情報は必ず記載してください。情報がない場合は同業他社や一般的な情報から妥当な内容を推測してください。

最後に、この企業の特徴やポイントを簡潔にまとめてください。
"""

            # プロンプトの長さをログに記録
            logger.info(f"プロンプト長: {len(prompt)} 文字")
            
            # OpenAIでレポート生成
            logger.info(f"レポート生成開始: {company_name}")
            logger.info(f"使用するモデル: {self.model_name}")
            
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "あなたは企業分析のエキスパートです。与えられた企業情報を分析し、詳細な企業レポートを作成します。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5
            )
            
            report = response.choices[0].message.content
            
            # レポートの要約統計をログに記録
            sentences = report.split('。')
            paragraphs = report.split('\n\n')
            logger.info(f"生成されたレポート統計: {len(report)} 文字, 約 {len(sentences)} 文, {len(paragraphs)} 段落")
            
            # レポートをフォーマット
            formatted_report = format_report(report)
            
            logger.info(f"レポート生成完了: {company_name}")
            return {"success": True, "report": formatted_report}
        
        except Exception as e:
            logger.error(f"レポート生成中にエラーが発生しました: {str(e)}")
            return {"error": str(e)}