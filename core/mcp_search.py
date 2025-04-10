"""MCPベースの詳細検索機能"""

import logging
import sys
import os
import json
import re
from urllib.parse import urlparse

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

# 除外すべきドメインのリスト
EXCLUDED_DOMAINS = [
    "wikipedia.org",
    "wikimedia.org",
    "wiktionary.org",
    "wikihow.com",
    "reddit.com",
    "quora.com",
    "twitter.com",
    "facebook.com",
    "instagram.com"
]

def generate_search_queries(query, process_log=None):
    """検索クエリを生成する"""
    try:
        prompt = """あなたは企業調査のエキスパートです。企業に関する以下の基本情報を収集するための最も効果的な検索クエリを5つ生成してください：
        
        - 代表取締役と経営陣の情報
        - 企業概要（設立年、資本金、従業員数など）
        - 企業理念・ミッション・ビジョン
        - 主要事業・サービス
        - 業績情報・財務情報
        
        特に、公式サイトや信頼性の高いビジネスメディアからの情報を見つけるためのクエリを考えてください。
        Wikipediaや編集可能なサイトは信頼性が低いため、そこからの情報は避けるようにしてください。
        
        Pythonリストの形式で返してください。例: ['[企業名] 代表取締役 プロフィール', '[企業名] 企業概要 公式', ...]
        
        絶対に具体的な検索クエリのみを返してください。追加のテキストは含めないでください。"""
            
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "あなたは企業分析の専門家です。"},
                {"role": "user", "content": f"企業名: {query}\n\n{prompt}"}
            ]
        )
        
        response_text = response.choices[0].message.content
        
        # プロセスログに追加
        if process_log is not None:
            process_log.append({
                "step": "検索クエリ生成",
                "input": query,
                "output": response_text
            })
        
        # リスト部分を抽出
        if '[' in response_text and ']' in response_text:
            list_part = response_text[response_text.find('['):response_text.rfind(']')+1]
            try:
                search_queries = eval(list_part)
                if isinstance(search_queries, list) and len(search_queries) > 0:
                    # 基本的な企業情報に関するクエリを確実に含める
                    base_queries = [
                        f"{query} 代表取締役 プロフィール 公式",
                        f"{query} 企業概要 会社概要 公式サイト",
                        f"{query} 設立年 資本金 従業員数 公式発表",
                        f"{query} 企業理念 ミッション ビジョン バリュー",
                        f"{query} 事業内容 主要事業 サービス",
                        f"{query} 業績 財務情報 決算 IR"
                    ]
                    
                    # 重複を削除しながら両方のリストを結合
                    all_queries = list(set(base_queries + search_queries))
                    
                    return all_queries[:10]  # 最大10件に制限
                return base_queries
            except:
                return [f"{query} 企業情報 公式"]
        else:
            # リストが見つからない場合はデフォルトのクエリを返す
            logger.warning(f"LLMレスポンスにリストが見つかりません: {response_text}")
            return [
                f"{query} 代表取締役 プロフィール 公式",
                f"{query} 企業概要 会社概要 公式サイト",
                f"{query} 設立年 資本金 従業員数 公式発表",
                f"{query} 企業理念 ミッション ビジョン バリュー",
                f"{query} 事業内容 主要事業 サービス",
                f"{query} 業績 財務情報 決算 IR"
            ]
    except Exception as e:
        logger.error(f"検索クエリ生成でエラー発生: {e}")
        if process_log is not None:
            process_log.append({
                "step": "検索クエリ生成エラー",
                "error": str(e)
            })
        return [
            f"{query} 代表取締役 公式",
            f"{query} 企業概要 公式",
            f"{query} 事業内容 公式"
        ]

def web_search(query: str, process_log=None) -> list:
    """Tavily APIを使用してウェブ検索を行い、関連リンクのリストを返す"""
    links = []
    try:
        logger.info(f"Tavilyで検索: {query}")
        
        # 検索を実行し、結果を取得
        search_response = tavily.search(
            query=query,
            search_depth="advanced",
            max_results=8,         # より多くの結果を取得
            include_domains=[],
            exclude_domains=EXCLUDED_DOMAINS  # Wikipediaなどを除外
        )
        
        # レスポンスからリンクを抽出
        if "results" in search_response:
            for result in search_response["results"]:
                if "url" in result:
                    # URLが除外ドメインでないことを確認
                    url = result["url"]
                    domain = urlparse(url).netloc
                    if not any(excluded in domain for excluded in EXCLUDED_DOMAINS):
                        links.append({
                            "url": url,
                            "title": result.get("title", ""),
                            "content_preview": result.get("content", "")[:200],
                            "domain": domain
                        })
            logger.info(f"Tavily検索で{len(links)}個のリンクを返しました")
            
            # プロセスログに追加
            if process_log is not None:
                process_log.append({
                    "step": "ウェブ検索",
                    "query": query,
                    "results": links
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
        
    return links

def is_official_site(url, company_name):
    """URLが会社の公式サイトかどうかを判断する"""
    domain = urlparse(url).netloc.lower()
    company_name_parts = company_name.lower().split()
    
    # '.co.jp'や'.com'などが含まれているか
    if any(tld in domain for tld in ['.co.jp', '.com', '.jp', '.net']):
        # 会社名の各部分がドメインに含まれているか
        for part in company_name_parts:
            if len(part) > 2 and part in domain:  # 短すぎる部分（「株式会社」の「株」など）は除外
                return True
    
    return False

def extract_webpage_content(urls, company_name, process_log=None):
    """Tavily Extract APIを使用してウェブページの内容を取得する"""
    try:
        if not urls:
            return []
        
        logger.info(f"Tavily Extractで{len(urls)}件のURLからコンテンツを抽出します")
        
        # URLをソート - 公式サイトを優先
        sorted_urls = sorted(urls, key=lambda x: (not is_official_site(x["url"], company_name), x["url"]))
        
        # URLリストのみを抽出（最大5件）
        url_list = [item["url"] for item in sorted_urls[:5] if "url" in item]
        
        # Tavily Extract APIを呼び出し
        extract_response = tavily.extract(
            urls=url_list,
            extract_depth="advanced",
            include_images=True
        )
        
        extracted_contents = []
        
        # レスポンスを処理
        if isinstance(extract_response, dict) and "results" in extract_response:
            for result in extract_response["results"]:
                content = {
                    "url": result.get("url", ""),
                    "title": result.get("title", ""),
                    "content": result.get("content", ""),
                    "images": result.get("images", []),
                    "is_official": is_official_site(result.get("url", ""), company_name)
                }
                extracted_contents.append(content)
                
            logger.info(f"Tavily Extractで{len(extracted_contents)}件のコンテンツを抽出しました")
            
            # プロセスログに追加
            if process_log is not None:
                process_log.append({
                    "step": "ウェブページ抽出",
                    "urls": url_list,
                    "extracted_count": len(extracted_contents),
                    "official_site_count": sum(1 for content in extracted_contents if content["is_official"])
                })
                
            return extracted_contents
        else:
            logger.warning(f"Tavily Extractが正しい結果を返しませんでした: {extract_response}")
            if process_log is not None:
                process_log.append({
                    "step": "ウェブページ抽出エラー",
                    "urls": url_list,
                    "error": "Extractが正しい結果を返しませんでした"
                })
            return []
            
    except Exception as e:
        logger.error(f"Tavily Extractでエラー発生: {str(e)}")
        if process_log is not None:
            process_log.append({
                "step": "ウェブページ抽出エラー",
                "error": str(e)
            })
        return []

def analyze_content_relevance(query, content, process_log=None):
    """コンテンツの関連性、有用性、信頼性を分析する"""
    if not content:
        return None
    
    prompt = """あなたは企業分析の専門家です。以下のウェブページコンテンツを分析し、企業に関する重要な情報を抽出してください。

特に以下の情報に注目してください：
1. 代表取締役と経営陣の情報
2. 企業概要（設立年、資本金、従業員数など）
3. 企業理念・ミッション・ビジョン
4. 主要事業・サービス内容
5. 業績情報・財務情報

また、このコンテンツの信頼性も評価してください。公式サイト、政府機関、信頼できるビジネスメディアからの情報は信頼性が高いとみなします。
逆に、ウィキペディアのような誰でも編集できるサイト、個人ブログ、SNS投稿などは信頼性が低いとみなします。

関連する重要な情報を抽出し、以下の形式で返してください：

```json
{
  "relevance": 0-10（このコンテンツの関連性を0〜10で評価）,
  "reliability": 0-10（このコンテンツの信頼性を0〜10で評価）,
  "extracted_info": {
    "management": "代表取締役と経営陣に関する情報",
    "company_profile": "企業概要に関する情報",
    "philosophy": "企業理念に関する情報",
    "business": "事業内容に関する情報",
    "performance": "業績に関する情報",
    "other": "その他の重要情報"
  },
  "source_evaluation": "情報源に関するコメント（公式サイト、信頼できるメディアなど）"
}
```

各項目は、情報が見つからない場合は空にしてください。JSONのみを返してください。"""

    try:
        webpage_title = content.get("title", "無題")
        webpage_content = content.get("content", "")
        is_official = content.get("is_official", False)
        
        if not webpage_content:
            return None
            
        # 内容が長すぎる場合は切り詰める
        if len(webpage_content) > 10000:
            webpage_content = webpage_content[:10000] + "..."
        
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "あなたは企業分析の専門家です。"},
                {"role": "user", "content": f"企業名: {query}\nウェブページタイトル: {webpage_title}\n公式サイト: {'はい' if is_official else 'いいえ'}\nURL: {content.get('url', '')}\nコンテンツ:\n{webpage_content}\n\n{prompt}"}
            ],
            response_format={"type": "json_object"}
        )
        
        result_text = response.choices[0].message.content
        
        try:
            result = json.loads(result_text)
            
            # プロセスログに追加
            if process_log is not None:
                process_log.append({
                    "step": "コンテンツ分析",
                    "url": content.get("url", ""),
                    "title": webpage_title,
                    "relevance": result.get("relevance", 0),
                    "reliability": result.get("reliability", 0),
                    "extracted_fields": list(result.get("extracted_info", {}).keys())
                })
            
            # 関連性スコアが低い場合はNoneを返す
            if result.get("relevance", 0) < 3 or result.get("reliability", 0) < 3:
                return None
                
            return {
                "url": content.get("url", ""),
                "title": webpage_title,
                "relevance": result.get("relevance", 0),
                "reliability": result.get("reliability", 0),
                "extracted_info": result.get("extracted_info", {}),
                "source_evaluation": result.get("source_evaluation", ""),
                "is_official": is_official,
                "images": content.get("images", [])
            }
            
        except json.JSONDecodeError:
            logger.error(f"JSON解析エラー: {result_text}")
            if process_log is not None:
                process_log.append({
                    "step": "コンテンツ分析エラー",
                    "url": content.get("url", ""),
                    "error": "結果のJSON解析に失敗"
                })
            return None
            
    except Exception as e:
        logger.error(f"コンテンツ分析エラー: {str(e)}")
        if process_log is not None:
            process_log.append({
                "step": "コンテンツ分析エラー",
                "error": str(e)
            })
        return None

def compile_company_info(company_name, analyzed_results, process_log=None):
    """複数の分析結果から包括的な企業情報を編集する"""
    if not analyzed_results:
        return {"content": f"{company_name}の企業情報が見つかりませんでした。", "images": []}
        
    # 関連性と信頼性の重み付けでソート（公式サイトを優先）
    def sort_key(result):
        relevance = result.get("relevance", 0)
        reliability = result.get("reliability", 0)
        is_official = 10 if result.get("is_official", False) else 0
        return (is_official, relevance + reliability)
    
    sorted_results = sorted(analyzed_results, key=sort_key, reverse=True)
    
    # 各カテゴリの情報を集約
    compiled_info = {
        "management": [],
        "company_profile": [],
        "philosophy": [],
        "business": [],
        "performance": [],
        "other": []
    }
    
    # 情報源を追跡
    sources = []
    image_urls = []
    
    # 各結果から情報を抽出
    for result in sorted_results:
        source = {
            "url": result.get("url", ""),
            "title": result.get("title", ""),
            "is_official": result.get("is_official", False),
            "reliability": result.get("reliability", 0)
        }
        sources.append(source)
        
        extracted_info = result.get("extracted_info", {})
        for category, info in extracted_info.items():
            if info and category in compiled_info:
                # すでに同じ情報がないか確認（重複を避ける）
                is_duplicate = False
                for existing_info in compiled_info[category]:
                    if similarity(info, existing_info) > 0.7:  # 70%以上類似していれば重複とみなす
                        is_duplicate = True
                        break
                
                if not is_duplicate:
                    compiled_info[category].append(info)
                
        # 画像URLも収集
        for image in result.get("images", []):
            if isinstance(image, str) and image not in image_urls:
                image_urls.append(image)
    
    # 最終的なテキストを構築
    sections = [
        f"# {company_name}の企業分析\n",
    ]
    
    # 経営陣情報（必ず含める）
    if compiled_info["management"]:
        sections.append("## 経営陣情報\n" + "\n".join(compiled_info["management"]))
    else:
        sections.append(f"## 経営陣情報\n{company_name}の経営陣に関する具体的な情報は現在入手できません。最新の情報は公式サイトでご確認ください。")
    
    # 企業概要（必ず含める）
    if compiled_info["company_profile"]:
        sections.append("## 企業概要\n" + "\n".join(compiled_info["company_profile"]))
    else:
        sections.append(f"## 企業概要\n{company_name}の設立年、資本金、従業員数などの基本情報は現在入手できません。")
    
    # 企業理念
    if compiled_info["philosophy"]:
        sections.append("## 企業理念\n" + "\n".join(compiled_info["philosophy"]))
    else:
        sections.append(f"## 企業理念\n{company_name}の企業理念、ミッション、ビジョンに関する情報は見つかりませんでした。")
    
    # 事業内容（必ず含める）
    if compiled_info["business"]:
        sections.append("## 事業内容\n" + "\n".join(compiled_info["business"]))
    else:
        sections.append(f"## 事業内容\n{company_name}の主な事業内容や提供サービスに関する詳細情報は現在入手できません。")
    
    # 業績情報
    if compiled_info["performance"]:
        sections.append("## 業績情報\n" + "\n".join(compiled_info["performance"]))
    
    # その他の情報
    if compiled_info["other"]:
        sections.append("## その他の情報\n" + "\n".join(compiled_info["other"]))
    
    # 情報源
    sections.append("\n## 情報源")
    for i, source in enumerate(sources[:5], 1):  # 最大5つまで表示
        official_tag = "【公式】" if source["is_official"] else ""
        sections.append(f"{i}. {official_tag}[{source['title']}]({source['url']})")
    
    # 最終的なテキストを構築
    final_text = "\n\n".join(sections)
    
    # プロセスログに追加
    if process_log is not None:
        process_log.append({
            "step": "情報コンパイル",
            "company_name": company_name,
            "sections_with_content": [key for key, value in compiled_info.items() if value],
            "source_count": len(sources),
            "image_count": len(image_urls),
            "official_sources": sum(1 for source in sources if source["is_official"])
        })
    
    return {
        "content": final_text,
        "images": image_urls[:5]  # 最大5枚の画像を返す
    }

def similarity(text1, text2):
    """2つのテキストの類似度を計算する簡易な関数"""
    # 簡易的な実装 - 共通する単語の割合
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    
    if not words1 or not words2:
        return 0
    
    common_words = words1.intersection(words2)
    return len(common_words) / max(len(words1), len(words2))

def summarize_images(image_urls, company_name, process_log=None):
    """画像URLのリストを受け取り、各画像の説明を生成する"""
    if not image_urls:
        return {}
    
    result = {}
    try:
        for idx, img_url in enumerate(image_urls[:3]):  # 最大3枚の画像を処理
            try:
                # GPT-4oを使用して画像を説明
                completion = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"これは{company_name}に関連する画像です。この画像を簡潔に説明してください。企業のロゴや製品、オフィス、経営陣などの特徴を捉えてください。"
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": img_url
                                    }
                                }
                            ]
                        }
                    ],
                    max_tokens=100
                )
                
                description = completion.choices[0].message.content
                
                # プロセスログに追加
                if process_log is not None:
                    process_log.append({
                        "step": "画像説明生成",
                        "image_url": img_url,
                        "description": description
                    })
                
                # 結果を格納
                key = f"image_{idx}"
                result[key] = {
                    "url": img_url,
                    "description": description
                }
                
            except Exception as e:
                logger.error(f"画像説明の生成エラー: {str(e)}")
                if process_log is not None:
                    process_log.append({
                        "step": "画像説明生成エラー",
                        "image_url": img_url,
                        "error": str(e)
                    })
        
        return result
    except Exception as e:
        logger.error(f"画像処理エラー: {str(e)}")
        if process_log is not None:
            process_log.append({
                "step": "画像処理エラー",
                "error": str(e)
            })
        return {}

@mcp.tool()
def search(query: str) -> str:
    """インターネット検索"""
    try:
        # 検索プロセスのログを記録
        process_log = []
        
        # 検索クエリを生成
        process_log.append({
            "step": "検索開始",
            "user_query": query
        })
        
        search_queries = generate_search_queries(query, process_log)
        
        # 各クエリで検索を実行し、結果をマージ
        all_search_results = []
        for search_query in search_queries:
            results = web_search(search_query, process_log)
            all_search_results.extend(results)
        
        # 重複するURLを削除
        unique_urls = {}
        for result in all_search_results:
            url = result.get("url")
            if url and url not in unique_urls:
                unique_urls[url] = result
        
        unique_results = list(unique_urls.values())
        
        # 最も関連性の高そうな最大10件のURLを選択
        selected_urls = unique_results[:10]
        
        # Tavily Extract APIを使用してウェブページのコンテンツを取得
        extracted_contents = extract_webpage_content(selected_urls, query, process_log)
        
        # 各コンテンツの関連性を分析
        analyzed_results = []
        for content in extracted_contents:
            analysis = analyze_content_relevance(query, content, process_log)
            if analysis:
                analyzed_results.append(analysis)
        
        # 最終的な企業情報をコンパイル
        compiled_info = compile_company_info(query, analyzed_results, process_log)
        content_text = compiled_info.get("content", "")
        image_urls = compiled_info.get("images", [])
        
        # 画像の説明を生成
        image_descriptions = summarize_images(image_urls, query, process_log)
        
        # 結果をまとめる
        result = {
            "content": content_text,
            "images": image_descriptions,
            "process_log": process_log
        }
        
        return json.dumps(result, ensure_ascii=False)
    
    except Exception as e:
        logger.error(f"search関数でエラー発生: {str(e)}")
        return json.dumps({
            "content": f"検索中にエラーが発生しました: {str(e)}",
            "images": {},
            "process_log": [{"step": "エラー", "error": str(e)}]
        }, ensure_ascii=False)

@mcp.tool()
def get_images(query: str) -> dict:
    '''企業に関連する画像を取得する'''
    logger.info(f"画像検索: {query}")
    
    # 検索プロセスのログを記録
    process_log = []
    
    try:
        # プロセスログに検索開始情報を追加
        process_log.append({
            "step": "画像検索開始",
            "query": query
        })
        
        # 1. まず企業のウェブサイトを見つける
        company_site_query = f"{query} 公式サイト 会社概要"
        search_results = web_search(company_site_query, process_log)
        
        # 会社のウェブサイトと思われるURLを抽出
        official_urls = []
        for result in search_results:
            url = result.get("url", "")
            if url and is_official_site(url, query):
                official_urls.append({"url": url})
        
        # 公式サイトが見つからない場合は一般的な検索結果を使用
        if not official_urls:
            official_urls = search_results[:3]
        
        # 2. URLからコンテンツを抽出（画像含む）
        extracted_contents = extract_webpage_content(official_urls, query, process_log)
        
        # 3. 画像URLを収集
        image_urls = []
        for content in extracted_contents:
            for image in content.get("images", []):
                if isinstance(image, str) and image not in image_urls:
                    image_urls.append(image)
        
        # 4. 画像の説明を生成
        image_descriptions = summarize_images(image_urls, query, process_log)
        
        # 5. 画像が見つからない場合はロゴの検索を試みる
        if not image_descriptions:
            logo_query = f"{query} ロゴ logo 公式"
            logo_results = web_search(logo_query, process_log)
            logo_contents = extract_webpage_content(logo_results[:2], query, process_log)
            
            logo_urls = []
            for content in logo_contents:
                for image in content.get("images", []):
                    if isinstance(image, str) and image not in logo_urls:
                        logo_urls.append(image)
            
            image_descriptions = summarize_images(logo_urls, query, process_log)
        
        # 結果を返す
        if image_descriptions:
            result = {
                "images": image_descriptions,
                "process_log": process_log
            }
        else:
            # 画像が見つからない場合
            result = {
                "no_images": f"{query}に関連する画像を見つけることができませんでした。",
                "process_log": process_log
            }
            
        return result
            
    except Exception as e:
        logger.error(f"画像取得中にエラー発生: {str(e)}")
        return {
            "error": f"画像取得中にエラーが発生しました: {str(e)}",
            "process_log": process_log
        }

if __name__ == "__main__":
    mcp.run()