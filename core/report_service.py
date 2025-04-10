"""企業分析レポートを生成するサービス"""

from typing import Dict, Any, Optional
import logging
from openai import OpenAI

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
        self.model_name = settings.get("model_name", "gpt-4o-mini")
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
    
    def generate_report(
        self, 
        company_name: str, 
        company_info: str, 
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
            for section, included in report_sections.items():
                if included:
                    included_sections.append(section)
            
            # プロンプト作成
            prompt = f"""あなたは企業分析のエキスパートです。与えられた情報をもとに、{company_name}の企業分析レポートを作成してください。

企業に関する以下の情報を使って分析してください：
<企業情報>
{company_info}
</企業情報>

{sections_description}

次のセクションを含めてレポートを作成してください：{", ".join(included_sections)}

以下の点に注意してください：
1. 情報がない場合は「情報なし」と記載せず、そのセクションを省略してください。
2. 必ず日本語で出力してください。
3. 指定したセクションに関する情報を優先的に含めてください。
4. データに基づく具体的な分析を含めてください。
5. ウェブサイトからの情報がある場合はそれを参照してください。
6. レポートはマークダウン形式で作成してください。

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
                temperature=0.3
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