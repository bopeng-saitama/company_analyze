"""MCPベースの詳細検索機能"""

import logging
import sys
import os
import json
import re
import requests
from urllib.parse import urlparse
import tempfile
import io
import base64
import fitz  # PyMuPDF
from bs4 import BeautifulSoup

# プロジェクトのルートディレクトリをPythonパスに追加
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.fastmcp import FastMCP
from openai import OpenAI
from tavily import TavilyClient

from config.settings import get_settings

logger = logging.getLogger(__name__)

mcp = FastMCP("company_research")

# 設定からAPIキーを取得
settings = get_settings()
openai_api_key = settings.get("openai_api_key", "")
tavily_api_key = settings.get("tavily_api_key", "")
model_name = settings.get("model_name", "gpt-4o-mini")

# OpenAIクライアント初期化
client = OpenAI(api_key=openai_api_key)

# Tavilyクライアント初期化
tavily = TavilyClient(api_key=tavily_api_key)

def generate_query(query, sections=None, process_log=None, stream=False):
    """検索クエリを生成する"""
    try:
        # セクションに基づいてプロンプトを調整
        section_queries = {
            "companyOverview": "企業概要 会社概要 事業概要",
            "management": "代表取締役 役員一覧 経営陣 取締役 社長",
            "philosophy": "企業理念 経営理念 ミッション ビジョン 企業価値観",
            "establishment": "設立年 創業 資本金 株式 事業拠点 本社所在地",
            "businessDetails": "事業内容 主要製品 サービス内容 ビジネスモデル",
            "performance": "業績 売上高 営業利益 経常利益 純利益 財務状況",
            "growth": "成長戦略 中期計画 売上成長率 新規事業 事業拡大",
            "economicImpact": "景気動向 経済影響 業績推移 景況感",
            "competitiveness": "競争優位性 競合他社 市場シェア 技術力 特許",
            "culture": "社風 企業文化 組織風土 人員構成 男女比率",
            "careerPath": "キャリア形成 昇進制度 昇給 人事評価 平均勤続年数",
            "jobTypes": "職種 採用職種 必要スキル 専門職",
            "workingConditions": "勤務条件 給与水準 勤務地 勤務時間 休日 福利厚生",
            "csrActivity": "CSR活動 社会貢献 環境対策 ダイバーシティ SDGs",
            "relatedCompanies": "関連企業 子会社 親会社 グループ会社 提携企業"
        }
        
        # 企業名を抽出
        company_name = query.split()[0] if query else ""
        
        # 選択されたセクションに基づいてクエリ部分を構築
        query_parts = []
        if sections:
            for section, include in sections.items():
                if include and section in section_queries:
                    query_parts.append(section_queries[section])
        
        # セクションが選択されていない場合や選択が無効な場合はデフォルトのセクションを使用
        if not query_parts:
            # 基本情報のセクションを必ず含める
            for section in ["management", "establishment", "companyOverview", "businessDetails"]:
                query_parts.append(section_queries[section])
        
        # クエリを生成するプロンプト
        sections_text = " ".join(query_parts)
        prompt = f"""あなたは調査のエキスパートです。
        以下の企業に関する情報を効率的に検索するための最大4つのクエリを生成してください。
        
        企業名: {company_name}
        検索する情報: {sections_text}
        
        特に以下の情報を優先的に取得できるクエリを考えてください：
        - 代表取締役名や役員情報
        - 会社の設立年・資本金
        - 事業内容や主要製品・サービス
        
        Pythonリストの形式で返してください。例: ['クエリ1', 'クエリ2', 'クエリ3']
        必ず企業名を含めたクエリにしてください。
        """
            
        response = client.chat.completions.create(
            model=model_name,
            messages = [
                {"role": "system", "content": "あなたは役立つ正確な調査アシスタントです。"},
                {"role": "user", "content": prompt}
            ]
        )
        
        response_text = response.choices[0].message.content
        
        # プロセスログに追加
        if process_log is not None:
            process_log.append({
                "step": "検索クエリ生成",
                "input": prompt,
                "output": response_text
            })
        
        # リスト部分を抽出
        if '[' in response_text and ']' in response_text:
            list_part = response_text[response_text.find('['):response_text.rfind(']')+1]
            return list_part
        else:
            # リストが見つからない場合はデフォルトのクエリを返す
            logger.warning(f"LLMレスポンスにリストが見つかりません: {response_text}")
            default_queries = [
                f"{company_name} 代表取締役 役員一覧",
                f"{company_name} 会社概要 設立年 資本金",
                f"{company_name} 事業内容 主要製品 サービス",
                f"{company_name} 企業理念 経営理念"
            ]
            return str(default_queries)
    except Exception as e:
        logger.error(f"generate_queryでエラー発生: {e}")
        if process_log is not None:
            process_log.append({
                "step": "検索クエリ生成エラー",
                "error": str(e)
            })
        # エラー発生時のデフォルトクエリ
        company_name = query.split()[0] if query else ""
        default_queries = [
            f"{company_name} 代表取締役 役員一覧",
            f"{company_name} 会社概要 設立年 資本金",
            f"{company_name} 事業内容 主要製品 サービス"
        ]
        return str(default_queries)

def web_search(query: str, process_log=None) -> list:
    """Tavily APIを使用してウェブ検索を行い、関連リンクのリストを返す"""
    links = []
    try:
        logger.info(f"Tavilyで検索: {query}")
        
        # 検索を実行し、結果を取得
        search_response = tavily.search(
            query=query,
            search_depth="basic",  # "basic"または"advanced"
            max_results=5,         # 最大結果数
            include_domains=[],    # 任意：特定のドメインのみを含める
            exclude_domains=[]     # 任意：特定のドメインを除外
        )
        
        # レスポンスからリンクを抽出
        if "results" in search_response:
            for result in search_response["results"]:
                if "url" in result:
                    links.append(result["url"])
            logger.info(f"Tavily検索で{len(links)}個のリンクを返しました")
            
            # プロセスログに追加
            if process_log is not None:
                process_log.append({
                    "step": "ウェブ検索",
                    "query": query,
                    "results": [{"url": result.get("url", ""), "title": result.get("title", "")} 
                              for result in search_response["results"] if "url" in result]
                })
        else:
            logger.warning(f"Tavilyが結果を返しませんでした。レスポンス: {search_response}")
            if process_log is not None:
                process_log.append({
                    "step": "ウェブ検索",
                    "query": query,
                    "error": "検索結果がありません"
                })
            
    except Exception as e:
        logger.error(f"Tavily検索でエラー発生: {str(e)}")
        # プロセスログに追加
        if process_log is not None:
            process_log.append({
                "step": "ウェブ検索エラー",
                "query": query,
                "error": str(e)
            })
        # 検索が失敗した場合のフォールバックリンク
        links = ["https://example.com/search-failed"]
        
    return links

def if_useful(query: str, page_text: str, process_log=None):
    """ページの内容が有用かどうかを判断する"""
    prompt = """あなたは批判的な調査評価者です。ユーザーのクエリとウェブページの内容を考慮して、そのウェブページがクエリに関連する有用な情報を含んでいるかどうかを判断してください。
    企業の基本情報(代表取締役、設立年、資本金、事業内容など)に関する情報があれば特に重要と判断してください。
    「はい」または「いいえ」の一語で回答してください。余分なテキストは含めないでください。"""
    
    response = client.chat.completions.create(
        model=model_name,
        messages = [
            {"role": "system", "content": "あなたは調査の関連性を評価する厳格で簡潔な評価者です。"},
            {"role": "user", "content": f"ユーザークエリ: {query}\n\nウェブページ内容（最初の20000文字）:\n{page_text[:20000]}\n\n{prompt}"}
        ]
    )
    
    response = response.choices[0].message.content
    
    # プロセスログに追加（ページの内容は長すぎるので省略）
    if process_log is not None:
        process_log.append({
            "step": "有用性評価",
            "url_content_preview": page_text[:200] + "..." if len(page_text) > 200 else page_text,
            "evaluation": response
        })
    
    if response:
        answer = response.strip()
        if answer in ["はい", "いいえ", "Yes", "No"]:
            return "Yes" if answer in ["はい", "Yes"] else "No"
        else:
            # フォールバック: レスポンスからYes/Noを抽出
            if "はい" in answer or "Yes" in answer:
                return "Yes"
            elif "いいえ" in answer or "No" in answer:
                return "No"
    return "No"

def extract_relevant_context(query, search_query, page_text, process_log=None):
    """ページから照会に関連する内容を抽出する"""
    prompt = """あなたは情報抽出のエキスパートです。ユーザーのクエリ、このページに至った検索クエリ、およびウェブページの内容を考慮して、企業に関する以下の情報を優先的に抽出してください：

1. 代表取締役や役員に関する情報（名前、経歴など）
2. 会社の基本情報（設立年、資本金、本社所在地など）
3. 事業内容（主要製品、サービス、ビジネスモデルなど）
4. 企業理念や経営方針
5. 業績や財務情報
6. その他、企業分析に有用な情報

情報を箇条書きで構造化し、各項目には見出しをつけてください。例：
「代表取締役: 山田太郎」
「設立年: 1980年」
「資本金: 1億円」

明確に記載されている情報のみを抽出し、推測は避けてください。
"""
    
    response = client.chat.completions.create(
        model=model_name,
        messages = [
            {"role": "system", "content": "あなたは関連情報の抽出と要約のエキスパートです。"},
            {"role": "user", "content": f"ユーザークエリ: {query}\n検索クエリ: {search_query}\n\nウェブページ内容（最初の20000文字）:\n{page_text[:20000]}\n\n{prompt}"}
        ]
    )
    
    response = response.choices[0].message.content
    
    # プロセスログに追加
    if process_log is not None:
        process_log.append({
            "step": "情報抽出",
            "query": query,
            "search_query": search_query,
            "extracted_content": response
        })
    
    if response:
        return response.strip()
    return ""

def get_new_search_queries(user_query, previous_search_queries, all_contexts, process_log=None, sections=None):
    """既存の結果に基づいて、さらに検索が必要かどうかを決定する"""
    context_combined = "\n".join(all_contexts)
    
    # 重要な情報カテゴリを定義
    important_categories = [
        "代表取締役", "役員", "取締役", "社長", 
        "設立年", "創業", "資本金", 
        "事業内容", "主要製品", "サービス", 
        "企業理念", "経営理念"
    ]
    
    # 選択されたセクションからキーワードを抽出
    selected_categories = []
    if sections:
        section_keywords = {
            "management": ["代表取締役", "役員", "取締役", "社長"],
            "establishment": ["設立年", "創業", "資本金", "本社所在地"],
            "businessDetails": ["事業内容", "主要製品", "サービス", "ビジネスモデル"],
            "philosophy": ["企業理念", "経営理念", "ミッション", "ビジョン"]
        }
        
        for section, include in sections.items():
            if include and section in section_keywords:
                selected_categories.extend(section_keywords[section])
    
    # 選択されたカテゴリがない場合は重要なカテゴリを使用
    if not selected_categories:
        selected_categories = important_categories
    
    prompt = f"""あなたは分析的な調査アシスタントです。元のクエリ、これまで実行された検索クエリ、およびウェブページから抽出されたコンテキストに基づいて、さらなる調査が必要かどうかを判断してください。

特に以下の情報が不足している場合は、それらを取得するための新しい検索クエリを提供してください：
{', '.join(selected_categories)}

すでに収集された情報：
{context_combined}

さらなる調査が必要な場合は、Pythonリストとして最大4つの新しい検索クエリを提供してください（例：['新しいクエリ1', '新しいクエリ2']）。さらなる調査が不要であると判断した場合は、空の文字列「」で回答してください。
Pythonリストまたは空の文字列のみを出力し、追加のテキストは含めないでください。"""
    
    response = client.chat.completions.create(
        model=model_name,
        messages = [
            {"role": "system", "content": "あなたは関連情報の抽出と要約のエキスパートです。"},
            {"role": "user", "content": f"ユーザークエリ: {user_query}\n以前の検索クエリ: {previous_search_queries}\n\n{prompt}"}
        ]
    )
    
    response = response.choices[0].message.content
    
    # プロセスログに追加
    if process_log is not None:
        process_log.append({
            "step": "次の検索クエリ決定",
            "previous_queries": previous_search_queries,
            "decision": response
        })
    
    if response:
        cleaned = response.strip()
        if cleaned == "":
            return ""
        try:
            new_queries = eval(cleaned)
            if isinstance(new_queries, list):
                return new_queries
            else:
                logger.info(f"LLMが新しい検索クエリのリストを返しませんでした。レスポンス: {response}")
                return []
        except Exception as e:
            logger.error(f"新しい検索クエリの解析エラー:{e}, レスポンス:{response}")
            return []
    return []

def extract_text_from_pdf(url):
    """PDFからテキストを抽出する"""
    try:
        # PDFをダウンロード
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return f"PDFのダウンロードに失敗しました: {response.status_code}"
        
        # PDFをメモリ上で開く
        with fitz.open(stream=response.content, filetype="pdf") as doc:
            text = ""
            for page in doc:
                text += page.get_text()
            
            # 役員情報をより正確に抽出するためのパターン
            officer_pattern = r"(代表取締役|取締役会?長?|社長|執行役員|役員一覧)(.*?)(?=\n\n|$)"
            officers = re.findall(officer_pattern, text, re.DOTALL)
            
            if officers:
                for title, content in officers:
                    text += f"\n\n{title}:\n{content.strip()}\n"
            
            return text
    except Exception as e:
        return f"PDFの解析エラー: {str(e)}"

def extract_structured_data_from_html(html_content):
    """HTMLから構造化データを抽出する"""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 役員情報を探す
        officer_data = ""
        
        # 役員情報を含む可能性のある要素
        officer_keywords = ["役員", "取締役", "代表", "社長", "経営陣", "執行役員"]
        
        # h1, h2, h3, h4, h5, h6, thなどの見出し要素を検索
        for keyword in officer_keywords:
            # 見出し要素を検索
            headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'th'], string=lambda text: keyword in text if text else False)
            for heading in headings:
                # 見出しの次の要素を取得 (テーブルや段落)
                next_element = heading.find_next(['table', 'p', 'div', 'ul', 'ol'])
                if next_element:
                    officer_data += f"{heading.get_text(strip=True)}:\n{next_element.get_text(strip=True)}\n\n"
        
        # テーブルから役員情報を抽出
        tables = soup.find_all('table')
        for table in tables:
            table_text = table.get_text()
            if any(keyword in table_text for keyword in officer_keywords):
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if cells:
                        officer_data += " | ".join([cell.get_text(strip=True) for cell in cells]) + "\n"
        
        return officer_data if officer_data else ""
    
    except Exception as e:
        return f"HTML解析エラー: {str(e)}"

def fetch_webpage_text(url, process_log=None):
    """ウェブページの内容を取得する"""
    try:
        # URLの種類を判断
        is_pdf = url.lower().endswith('.pdf')
        
        if is_pdf:
            # PDFファイルの場合
            logger.info(f"PDFファイルを処理中: {url}")
            page_text = extract_text_from_pdf(url)
            
            # プロセスログに追加
            if process_log is not None:
                process_log.append({
                    "step": "PDFファイル処理",
                    "url": url,
                    "content_preview": page_text[:200] + "..." if len(page_text) > 200 else page_text
                })
            
            return page_text
        
        # 通常のウェブページの場合
        # URLからドメインまたはパスを抽出
        domain = re.sub(r'https?://', '', url)
        domain = domain.split('/')[0]  # ドメイン部分を取得
        query = f"website information {domain}"
        
        # 空でないクエリとURLドメインを使用
        logger.info(f"クエリ:'{query}'とURL:{url}でコンテンツを取得しています")
        search_response = tavily.search(
            query=query,
            search_depth="basic",
            include_domains=[url],  # この特定のURLのみを含める
            max_results=1
        )
        
        content = ""
        html_content = ""
        
        if "results" in search_response and search_response["results"]:
            result = search_response["results"][0]
            if "content" in result:
                content = result["content"]
                
                # HTMLコンテンツを取得（あれば）
                if "raw_content" in result:
                    html_content = result["raw_content"]
            
            # HTMLから構造化データを抽出
            if html_content:
                structured_data = extract_structured_data_from_html(html_content)
                if structured_data:
                    content += "\n\n構造化データ:\n" + structured_data
        
            # プロセスログに追加
            if process_log is not None:
                content_preview = content[:200] + "..." if len(content) > 200 else content
                process_log.append({
                    "step": "ウェブページ取得",
                    "url": url,
                    "content_preview": content_preview
                })
            return content
        
        # Tavilyがコンテンツを返さない場合は空文字列を返す
        logger.warning(f"Tavilyが{url}のコンテンツを返しませんでした")
        if process_log is not None:
            process_log.append({
                "step": "ウェブページ取得",
                "url": url,
                "error": "コンテンツを取得できませんでした"
            })
        return ""
    except Exception as e:
        logger.error(f"ウェブページテキストを取得中にエラー: {e}")
        if process_log is not None:
            process_log.append({
                "step": "ウェブページ取得エラー",
                "url": url,
                "error": str(e)
            })
        return ""
    
def process_link(link, query, search_query, process_log=None):
    """単一のリンクを処理する：コンテンツの取得、有用かどうかの判断、関連コンテンツの抽出"""
    logger.info(f"コンテンツを取得中: {link}")
    page_text = fetch_webpage_text(link, process_log)
    if not page_text:
        return None
    usefulness = if_useful(query, page_text, process_log)
    logger.info(f"{link}のページ有用性: {usefulness}")
    if usefulness == "Yes":
        context = extract_relevant_context(query, search_query, page_text, process_log)
        if context:
            logger.info(f"{link}から抽出されたコンテキスト（最初の200文字）: {context[:200]}")
            return context
    return None

def is_valid_image_url(url):
    """URLが有効な画像URLかどうかをチェックする"""
    # URLのパス部分を取得
    parsed_url = urlparse(url)
    path = parsed_url.path.lower()
    
    # 画像の拡張子をチェック
    valid_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.webp']
    if any(path.endswith(ext) for ext in valid_extensions):
        return True
    
    # Content-Typeをチェック
    try:
        # HEADリクエストを送信してContent-Typeを確認
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.head(url, headers=headers, timeout=3)
        content_type = response.headers.get('Content-Type', '')
        return content_type.startswith('image/')
    except:
        return False

def extract_company_description(company_name, process_log=None):
    """企業の説明を生成する"""
    try:
        prompt = f"""以下の企業について、1〜2文で簡潔に説明してください：
        {company_name}
        
        回答はできるだけ具体的で、企業の主要事業や特徴が伝わるようにしてください。"""
            
        response = client.chat.completions.create(
            model=model_name,
            messages = [
                {"role": "system", "content": "あなたは企業情報に詳しい専門家です。"},
                {"role": "user", "content": prompt}
            ]
        )
        
        description = response.choices[0].message.content
        
        # プロセスログに追加
        if process_log is not None:
            process_log.append({
                "step": "企業説明生成",
                "company": company_name,
                "description": description
            })
            
        return description
    except Exception as e:
        logger.error(f"企業説明の生成エラー: {e}")
        if process_log is not None:
            process_log.append({
                "step": "企業説明生成エラー",
                "company": company_name,
                "error": str(e)
            })
        return f"{company_name}に関する説明を生成できませんでした"

@mcp.tool()
def search(query: str, sections: dict = None) -> str:
    """インターネット検索"""
    try:
        # 検索プロセスのログを記録
        process_log = []
        
        iteration_limit = 3
        iteration = 0
        aggregated_contexts = []  
        all_search_queries = []   
        
        # 企業名を抽出
        company_name = query.split()[0] if query else ""
        
        # 検索クエリを生成
        try:
            custom_queries = eval(generate_query(query, sections, process_log))
            if isinstance(custom_queries, list) and len(custom_queries) > 0:
                new_search_queries = custom_queries
            else:
                logger.warning(f"LLMが有効なクエリリストを返しませんでした。デフォルトクエリを使用します")
                # デフォルトクエリ
                new_search_queries = [
                    f"{company_name} 代表取締役 役員一覧",
                    f"{company_name} 会社概要 設立年 資本金",
                    f"{company_name} 事業内容 主要製品 サービス",
                    f"{company_name} 企業理念 経営理念"
                ]
        except Exception as e:
            logger.error(f"検索クエリの評価エラー: {e}")
            # デフォルトクエリ
            new_search_queries = [
                f"{company_name} 代表取締役 役員一覧",
                f"{company_name} 会社概要 設立年 資本金",
                f"{company_name} 事業内容 主要製品 サービス",
                f"{company_name} 企業理念 経営理念"
            ]
            
        all_search_queries.extend(new_search_queries)
        
        # プロセスログに検索開始情報を追加
        process_log.append({
            "step": "検索開始",
            "user_query": query,
            "sections": sections,
            "initial_search_queries": new_search_queries
        })
        
        while iteration < iteration_limit:
            logger.info(f"\n=== イテレーション {iteration + 1} ===")
            iteration_contexts = []
            
            # プロセスログにイテレーション情報を追加
            process_log.append({
                "step": "イテレーション開始",
                "iteration": iteration + 1,
                "search_queries": new_search_queries
            })
            
            # 各クエリに対して検索を実行
            search_results = []
            for q in new_search_queries:
                links = web_search(q, process_log)
                search_results.append(links)

            # 一意のリンクとそれに対応する検索クエリを収集
            unique_links = {}
            for idx, links in enumerate(search_results):
                query_text = new_search_queries[idx]
                for link in links:
                    if link not in unique_links:
                        unique_links[link] = query_text

            logger.info(f"このイテレーションで{len(unique_links)}個のユニークリンクを集約しました。")
            
            # プロセスログにリンク情報を追加
            process_log.append({
                "step": "リンク集約",
                "unique_links_count": len(unique_links),
                "links": list(unique_links.keys())
            })

            # 各リンクを処理：コンテンツ取得、有用性判断、関連コンテンツ抽出
            link_results = []
            for link in unique_links:
                result = process_link(link, query, unique_links[link], process_log)
                if result:
                    link_results.append(result)
            
            # 有用なコンテキストを収集
            for res in link_results:
                if res:
                    iteration_contexts.append(res)

            if iteration_contexts:
                aggregated_contexts.extend(iteration_contexts)
                
                # プロセスログにコンテキスト情報を追加
                process_log.append({
                    "step": "コンテキスト収集",
                    "iteration": iteration + 1,
                    "contexts_count": len(iteration_contexts),
                    "total_contexts": len(aggregated_contexts)
                })
            else:
                logger.info("このイテレーションでは有用なコンテキストが見つかりませんでした。")
                
                # プロセスログに情報を追加
                process_log.append({
                    "step": "コンテキスト収集",
                    "iteration": iteration + 1,
                    "message": "有用なコンテキストが見つかりませんでした"
                })

            # さらに検索が必要かどうかを決定
            new_search_queries = get_new_search_queries(query, all_search_queries, aggregated_contexts, process_log, sections)
            if new_search_queries == "":
                logger.info("LLMはさらなる調査が不要だと示しました。")
                
                # プロセスログに情報を追加
                process_log.append({
                    "step": "検索終了",
                    "reason": "LLMがさらなる調査は不要と判断"
                })
                break
            elif new_search_queries:
                logger.info(f"LLMが新しい検索クエリを提供:{new_search_queries}")
                all_search_queries.extend(new_search_queries)
            else:
                logger.info("LLMは新しい検索クエリを提供しませんでした。ループを終了します。")
                
                # プロセスログに情報を追加
                process_log.append({
                    "step": "検索終了",
                    "reason": "新しい検索クエリがありません"
                })
                break

            iteration += 1
        
        # コンテキストが不足している場合、企業の説明を生成
        if not aggregated_contexts:
            company_description = extract_company_description(company_name, process_log)
            aggregated_contexts.append(company_description)
        
        # 検索結果とプロセスログの両方を返す
        result = {
            "content": '\n\n'.join(aggregated_contexts) if aggregated_contexts else "検索では関連情報が見つかりませんでした。クエリを変更するか、より詳細な情報を提供してください。",
            "process_log": process_log
        }
        
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        logger.error(f"search関数でエラー発生: {str(e)}")
        return json.dumps({
            "content": f"検索中にエラーが発生しました: {str(e)}",
            "process_log": [{"step": "エラー", "error": str(e)}]
        }, ensure_ascii=False)

@mcp.tool()
def get_images(query: str) -> dict:
    '''画像リンクと説明を取得する'''
    logger.info(f"画像検索: {query}")
    
    # 検索プロセスのログを記録
    process_log = []
    
    result = {}
    try:
        # プロセスログに検索開始情報を追加
        process_log.append({
            "step": "画像検索開始",
            "query": query
        })
        
        # Tavilyを使用して関連コンテンツを検索（画像を含む可能性あり）
        search_response = tavily.search(
            query=f"{query} 画像 ロゴ 会社ロゴ 企業ロゴ",
            search_depth="advanced",
            max_results=10
        )
        
        # プロセスログに検索結果を追加
        if "results" in search_response:
            process_log.append({
                "step": "Tavily検索結果",
                "results_count": len(search_response["results"]),
                "results": [{"title": r.get("title", ""), "url": r.get("url", "")} 
                           for r in search_response["results"][:3]]  # 最初の3つだけログに記録
            })
        
        # Tavily結果から画像リンクを抽出
        image_links = []
        
        # まず明確な画像URLを収集
        if "results" in search_response:
            for item in search_response["results"]:
                # 結果に画像リンクが含まれている場合
                if "image_url" in item and item["image_url"]:
                    if is_valid_image_url(item["image_url"]):
                        image_links.append(item["image_url"])
                
                # URLが画像URLかどうかをチェック
                if "url" in item and is_valid_image_url(item["url"]):
                    image_links.append(item["url"])
        
        # フォールバック: 会社ロゴの標準的なURLパターン
        company_name = query.split()[0] if query else ""  # 最初の単語を企業名と仮定
        
        # 画像が見つからない場合のフォールバックデータ
        if not image_links:
            # 企業の説明文を生成
            company_description = extract_company_description(company_name, process_log)
            result["no_images"] = f"{company_name}の画像は見つかりませんでしたが、以下の情報があります: {company_description}"
            
            # プロセスログに情報を追加
            process_log.append({
                "step": "画像検索結果",
                "message": "画像が見つかりませんでした。テキスト説明を生成しました。"
            })
        else:
            # プロセスログに画像リンク情報を追加
            process_log.append({
                "step": "画像リンク抽出",
                "image_links_count": len(image_links),
                "image_links": image_links[:3]  # 最初の3つだけログに記録
            })
            
            # 会社の説明を生成
            company_description = extract_company_description(company_name, process_log)
            
            # 画像の代わりに会社説明を使用
            for i, img_src in enumerate(image_links[:2]):
                key = f"image_{i}"
                result[key] = {
                    "url": img_src,
                    "description": f"{company_name} - {company_description}"
                }
            
            process_log.append({
                "step": "画像説明生成",
                "message": "画像URLを保存し、企業説明を生成しました"
            })
            
    except Exception as e:
        logger.error(f"画像取得中にエラー発生: {str(e)}")
        result["error"] = f"画像取得中にエラーが発生しました: {str(e)}"
        
        # プロセスログにエラー情報を追加
        process_log.append({
            "step": "画像検索エラー",
            "error": str(e)
        })
    
    # 結果にプロセスログを追加
    result["process_log"] = process_log
    return result

if __name__ == "__main__":
    mcp.run()