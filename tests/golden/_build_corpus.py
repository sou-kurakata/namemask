"""golden corpus ビルダー（Planv2 §8.1）。

架空名のみ・実在名なし。各ケースの surface が text の部分文字列であることを
検証してから corpus.json を書き出す。手作業のオフセットずれを機械的に排除する。

実行:  python tests/golden/_build_corpus.py
"""

from __future__ import annotations

import json
from pathlib import Path

P = "PERSON"
O = "ORGANIZATION"
L = "LOCATION"
A = "ADDRESS"
E = "EMAIL"
H = "PHONE"
M = "MYNUMBER"

# チェックディジット検証済みのマイナンバー（tests での再計算と一致）
MYNUM_VALID_1 = "123456789018"
MYNUM_VALID_2 = "987654321093"
MYNUM_VALID_3 = "234567890121"
MYNUM_INVALID = "123456789019"  # チェックディジット不正 -> 検出対象外


def ent(surface: str, type_: str, nth: int | None = None) -> dict:
    d = {"surface": surface, "type": type_}
    if nth is not None:
        d["nth"] = nth
    return d


# (id, category, text, entities, note)
CASES: list[tuple] = [
    # ---- ORG 法人格 前置 ----
    ("org_pre_01", "org-prefix",
     "株式会社アオヤマ商事の件でご連絡いたしました。", [ent("株式会社アオヤマ商事", O)], ""),
    ("org_pre_02", "org-prefix",
     "本日、有限会社ミドリ設計と打ち合わせを行いました。", [ent("有限会社ミドリ設計", O)], ""),
    ("org_pre_03", "org-prefix",
     "合同会社サクラソフトウェアより見積が届いています。", [ent("合同会社サクラソフトウェア", O)], ""),
    ("org_pre_04", "org-prefix",
     "一般社団法人ヒカリ協会の理事会に出席します。", [ent("一般社団法人ヒカリ協会", O)], ""),
    ("org_pre_05", "org-prefix",
     "医療法人カモメ会の担当者に確認をお願いします。", [ent("医療法人カモメ会", O)], ""),
    # ---- ORG 法人格 後置 ----
    ("org_suf_01", "org-suffix",
     "ツバサ工業株式会社への発注書を作成しました。", [ent("ツバサ工業株式会社", O)], ""),
    ("org_suf_02", "org-suffix",
     "コハク物産有限会社の請求書を受領しました。", [ent("コハク物産有限会社", O)], ""),
    ("org_suf_03", "org-suffix",
     "ハルカゼ運輸合同会社と契約を締結しました。", [ent("ハルカゼ運輸合同会社", O)], ""),
    ("org_suf_04", "org-suffix",
     "セイリュウ建設株式会社の現場を視察しました。", [ent("セイリュウ建設株式会社", O)], ""),
    ("org_suf_05", "org-suffix",
     "ナナホシ食品株式会社より新製品の案内がありました。", [ent("ナナホシ食品株式会社", O)], ""),
    # ---- ORG 略記 (株) (有) ----
    ("org_abbr_01", "org-abbr",
     "(株)キリシマ電機の田中様よりお電話がありました。",
     [ent("(株)キリシマ電機", O), ent("田中", P)], ""),
    ("org_abbr_02", "org-abbr",
     "(有)ウミネコ商店の在庫を確認しました。", [ent("(有)ウミネコ商店", O)], ""),
    ("org_abbr_03", "org-abbr",
     "コンサルはヤマブキ総研(株)が担当します。", [ent("ヤマブキ総研(株)", O)], ""),
    ("org_abbr_04", "org-abbr",
     "（株）フジオカ製作所の納期は来週です。", [ent("（株）フジオカ製作所", O)], "全角括弧"),
    ("org_abbr_05", "org-abbr",
     "契約先は（有）シラユキ工房で確定しました。", [ent("（有）シラユキ工房", O)], "全角括弧"),
    # ---- ORG ㈱ 全角合字 ----
    ("org_glyph_01", "org-glyph",
     "㈱アカネテクノロジーとの提携を検討中です。", [ent("㈱アカネテクノロジー", O)], "㈱合字"),
    ("org_glyph_02", "org-glyph",
     "アサギリ物流㈱の配送状況を照会しました。", [ent("アサギリ物流㈱", O)], "㈱合字 後置"),
    ("org_glyph_03", "org-glyph",
     "㈲コトブキ商会に見積を依頼しました。", [ent("㈲コトブキ商会", O)], "㈲合字"),
    ("org_glyph_04", "org-glyph",
     "先方は㈱スミレデザインの佐藤課長です。",
     [ent("㈱スミレデザイン", O), ent("佐藤", P)], "㈱合字＋役職人名"),
    # ---- ORG 全角英数社名 ----
    ("org_fw_01", "org-fullwidth",
     "株式会社ＡＢＣ商事の担当にご連絡ください。", [ent("株式会社ＡＢＣ商事", O)], "全角英字"),
    ("org_fw_02", "org-fullwidth",
     "ＸＹＺ工業株式会社の見積を精査しました。", [ent("ＸＹＺ工業株式会社", O)], "全角英字"),
    ("org_fw_03", "org-fullwidth",
     "(株)ＫＭＴソリューションズと面談予定です。", [ent("(株)ＫＭＴソリューションズ", O)], "全角英字＋略記"),
    # ---- コア名のみ（辞書ケース。clients_test.csv 併設）----
    ("core_01", "org-core",
     "アオヤマ商事の追加発注について相談したいです。", [ent("アオヤマ商事", O)], "法人格なしコア名"),
    ("core_02", "org-core",
     "ミドリ設計とサクラソフトウェアの両社に見積依頼します。",
     [ent("ミドリ設計", O), ent("サクラソフトウェア", O)], "コア名複数"),
    ("core_03", "org-core",
     "キリシマ電機の納品は完了しています。", [ent("キリシマ電機", O)], "コア名"),
    ("core_04", "org-core",
     "ツバサ工業への支払いは月末締めです。", [ent("ツバサ工業", O)], "コア名"),
    ("core_05", "org-core",
     "ヤマブキ総研から届いたレポートを共有します。", [ent("ヤマブキ総研", O)], "コア名"),
    # ---- 漢字人名 敬称/役職 ----
    ("person_kanji_01", "person-kanji",
     "山田様より本日中に折り返しの依頼がありました。", [ent("山田", P)], "様"),
    ("person_kanji_02", "person-kanji",
     "田中さんに資料を送付しました。", [ent("田中", P)], "さん"),
    ("person_kanji_03", "person-kanji",
     "本件は佐藤部長の承認が必要です。", [ent("佐藤", P)], "役職 部長"),
    ("person_kanji_04", "person-kanji",
     "鈴木課長と高橋主任が同席します。",
     [ent("鈴木", P), ent("高橋", P)], "役職 複数"),
    ("person_kanji_05", "person-kanji",
     "渡辺社長宛に招待状をお送りください。", [ent("渡辺", P)], "役職 社長"),
    ("person_kanji_06", "person-kanji",
     "担当の小林様、伊藤様にも共有済みです。",
     [ent("小林", P), ent("伊藤", P)], "様 複数"),
    ("person_kanji_07", "person-kanji",
     "本件は佐々木様が担当します。", [ent("佐々木", P)], "繰返し記号々を含む姓（木のみ化の回帰）"),
    # ---- カタカナ人名 ----
    ("person_kana_01", "person-kana",
     "アンナ様からご質問をいただきました。", [ent("アンナ", P)], "カタカナ 様"),
    ("person_kana_02", "person-kana",
     "本日の通訳はマイケルさんにお願いします。", [ent("マイケル", P)], "カタカナ さん"),
    ("person_kana_03", "person-kana",
     "リサ主任とケビン氏が来社されます。",
     [ent("リサ", P), ent("ケビン", P)], "カタカナ 複数"),
    ("person_kana_04", "person-kana",
     "ソフィア先生の講演を予定しています。", [ent("ソフィア", P)], "カタカナ 先生"),
    # ---- メール署名ブロック（社名/氏名/電話/メール密集）----
    ("sig_01", "signature",
     "――――――\n株式会社アオヤマ商事\n営業部 山田太郎\nTEL: 03-1234-5678\nEmail: yamada@aoyama-example.co.jp\n――――――",
     [ent("株式会社アオヤマ商事", O), ent("山田太郎", P),
      ent("03-1234-5678", H), ent("yamada@aoyama-example.co.jp", E)], ""),
    ("sig_02", "signature",
     "ツバサ工業株式会社 開発部\n担当: 田中花子\n携帯 090-8765-4321\ntanaka.h@tsubasa-example.jp",
     [ent("ツバサ工業株式会社", O), ent("田中花子", P),
      ent("090-8765-4321", H), ent("tanaka.h@tsubasa-example.jp", E)], ""),
    ("sig_03", "signature",
     "㈱スミレデザイン\n佐藤健\nダイヤルイン 0120-000-111\nsato_k@sumire.example.com",
     [ent("㈱スミレデザイン", O), ent("佐藤健", P),
      ent("0120-000-111", H), ent("sato_k@sumire.example.com", E)], ""),
    ("sig_04", "signature",
     "ミドリ設計 設計課 鈴木一郎\nIP: 050-1111-2222 / suzuki@midori.example.net",
     [ent("ミドリ設計", O), ent("鈴木一郎", P),
      ent("050-1111-2222", H), ent("suzuki@midori.example.net", E)], ""),
    # ---- 全角電話 / ハイフン種混在 ----
    ("phone_fw_01", "phone-fullwidth",
     "お問い合わせは０３－１２３４－５６７８までお願いします。", [ent("０３－１２３４－５６７８", H)], "全角電話"),
    ("phone_fw_02", "phone-hyphen",
     "携帯番号は090ー1111ー2222です。", [ent("090ー1111ー2222", H)], "長音ハイフン"),
    ("phone_fw_03", "phone-hyphen",
     "代表電話 03‐9999‐0000 におかけください。", [ent("03‐9999‐0000", H)], "全角風ハイフン"),
    ("phone_fw_04", "phone-plain",
     "FAXは0664001234へ送信してください。", [ent("0664001234", H)], "ハイフンなし"),
    # ---- 全角英数メール ----
    ("email_fw_01", "email-fullwidth",
     "送付先はｉｎｆｏ＠ｅｘａｍｐｌｅ．ｃｏｍです。", [ent("ｉｎｆｏ＠ｅｘａｍｐｌｅ．ｃｏｍ", E)], "全角メール"),
    ("email_fw_02", "email-fullwidth",
     "受付：ｓａｌｅｓ＠ｔｅｓｔ．ｃｏ．ｊｐ 宛にご返信ください。", [ent("ｓａｌｅｓ＠ｔｅｓｔ．ｃｏ．ｊｐ", E)], "全角メール"),
    ("email_fw_03", "email-mixed",
     "連絡先は support＠example.jp です。", [ent("support＠example.jp", E)], "@のみ全角"),
    # ---- EMAIL 半角 ----
    ("email_01", "email",
     "詳細は contact@example.org までご連絡ください。", [ent("contact@example.org", E)], ""),
    ("email_02", "email",
     "請求書は billing.dept+inv@sub.example.co.jp に送ります。",
     [ent("billing.dept+inv@sub.example.co.jp", E)], "プラス記号入り"),
    # ---- PHONE 半角各種 ----
    ("phone_01", "phone",
     "固定電話は 06-6400-1234 です。", [ent("06-6400-1234", H)], "固定"),
    ("phone_02", "phone",
     "フリーダイヤル 0120-123-456 で受付中です。", [ent("0120-123-456", H)], "フリーダイヤル"),
    ("phone_03", "phone",
     "緊急連絡先: 080-1234-5678", [ent("080-1234-5678", H)], "携帯"),
    ("phone_04", "phone",
     "小笠原支所は04992-2-1234までお願いします。", [ent("04992-2-1234", H)], "5桁市外局番(小笠原)"),
    ("phone_05", "phone",
     "白川郷の窓口は05769-6-1234です。", [ent("05769-6-1234", H)], "5桁市外局番(白川村)"),
    # ---- マイナンバー 正 ----
    ("mynum_valid_01", "mynumber-valid",
     f"個人番号は{MYNUM_VALID_1}です。", [ent(MYNUM_VALID_1, M)], "有効"),
    ("mynum_valid_02", "mynumber-valid",
     f"マイナンバー {MYNUM_VALID_2} を記載します。", [ent(MYNUM_VALID_2, M)], "有効"),
    ("mynum_valid_03", "mynumber-valid",
     f"番号：{MYNUM_VALID_3}（本人確認済み）", [ent(MYNUM_VALID_3, M)], "有効"),
    # ---- マイナンバー 不正（チェックディジット不正 -> 検出しない）----
    ("mynum_invalid_01", "mynumber-invalid",
     f"入力された{MYNUM_INVALID}は桁誤りの可能性があります。", [], "無効CD=検出対象外"),
    ("mynum_invalid_02", "mynumber-invalid",
     "注文番号は123456789012ですのでご確認ください。", [], "12桁だがCD不正=検出対象外"),
    # ---- 誤検出トラップ: 日付を電話番号として拾わない ----
    ("trap_phone_01", "trap-phone",
     "提出締切は07-07-2026です。厳守してください。", [], "MM-DD-YYYY 日付"),
    ("trap_phone_02", "trap-phone",
     "イベントは03-15-2026に開催予定です。", [], "03始まりでも4-4でなければ電話でない"),
    # ---- 誤検出トラップ: 皆さん / お客様 ----
    ("trap_person_01", "trap-person",
     "皆さん、本日の会議にご参加ありがとうございました。", [], "皆さん"),
    ("trap_person_02", "trap-person",
     "お客様各位、平素より格別のご高配を賜り厚く御礼申し上げます。", [], "お客様"),
    ("trap_person_03", "trap-person",
     "奥様によろしくお伝えください。", [], "奥様"),
    # ---- 誤検出トラップ: 株式会社の制度説明文 ----
    ("trap_org_01", "trap-org",
     "株式会社とは、株式を発行して資金を調達する会社形態のことです。", [], "制度説明"),
    ("trap_org_02", "trap-org",
     "有限会社は現在新設できない会社形態です。", [], "制度説明"),
    # ---- 誤検出トラップ: 単独地名 ----
    ("trap_loc_01", "trap-loc",
     "来週は東京から大阪へ出張します。", [], "地名は初版で非対象"),
    ("trap_loc_02", "trap-loc",
     "北海道の気候について調べています。", [], "地名は初版で非対象"),
    ("trap_loc_03", "trap-loc",
     "東京都市部の再開発が進んでいます。", [], "都市部=複合語（住所層でも誤検出しない）"),
    ("trap_loc_04", "trap-loc",
     "京都府市場調査の報告書を提出。", [], "市場=複合語（住所層でも誤検出しない）"),
    # ---- 複合現実ケース ----
    ("mixed_01", "mixed",
     "株式会社アオヤマ商事の山田様より、(株)キリシマ電機の見積の件でご連絡をいただきました。",
     [ent("株式会社アオヤマ商事", O), ent("山田", P), ent("(株)キリシマ電機", O)], ""),
    ("mixed_02", "mixed",
     "田中様、㈱スミレデザインの佐藤課長と03-1234-5678で調整済みです。yamada@aoyama-example.co.jpにも共有しました。",
     [ent("田中", P), ent("㈱スミレデザイン", O), ent("佐藤", P),
      ent("03-1234-5678", H), ent("yamada@aoyama-example.co.jp", E)], ""),
    ("mixed_03", "mixed",
     "アオヤマ商事とアオヤマ商事の子会社は別法人です。アオヤマ商事宛に請求します。",
     [ent("アオヤマ商事", O)], "同一表記の複数出現"),
    ("mixed_04", "mixed",
     "ミドリ設計の鈴木一郎様（携帯 090-8765-4321）が窓口です。",
     [ent("ミドリ設計", O), ent("鈴木一郎", P), ent("090-8765-4321", H)], ""),
    ("mixed_05", "mixed",
     "本日、ツバサ工業株式会社の高橋主任、ナナホシ食品株式会社の伊藤様と会食しました。",
     [ent("ツバサ工業株式会社", O), ent("高橋", P),
      ent("ナナホシ食品株式会社", O), ent("伊藤", P)], ""),
    # ---- エッジ ----
    ("edge_empty", "edge",
     "", [], "空文字"),
    ("edge_symbols", "edge",
     "！＃＄％＆（）＊＋ーー――…", [], "記号のみ"),
    ("edge_multilang", "edge",
     "Please contact 山田様 at yamada@aoyama-example.co.jp regarding 株式会社アオヤマ商事.",
     [ent("山田", P), ent("yamada@aoyama-example.co.jp", E),
      ent("株式会社アオヤマ商事", O)], "多言語混在"),

    # ---- P3.5-1: 辞書ハイフン/空白バリアント（fold 影で照合）----
    # 辞書登録は「株式会社スカイーテック」（長音ー）。本文は別のハイフン種/空白。
    ("dict_var_01", "dict-variant",
     "スカイ−テックへの発注書を確認しました。", [ent("スカイ−テック", O)], "U+2212 マイナス"),
    ("dict_var_02", "dict-variant",
     "スカイ‐テック株式会社と契約を締結しました。", [ent("スカイ‐テック株式会社", O)], "U+2010 ハイフン＋法人格"),
    ("dict_var_03", "dict-variant",
     "アオヤマ　商事の追加発注についてご相談です。", [ent("アオヤマ　商事", O)], "全角空白挿入"),

    # ---- P3.5-2: 部署名＋人名＋敬称（左境界ガード）----
    ("person_dept_01", "person-dept",
     "営業部田中様より至急のご連絡がありました。", [ent("田中", P)], "部署食い込み是正"),
    ("person_dept_02", "person-dept",
     "経理部高橋主任が本件を担当します。", [ent("高橋", P)], "部署食い込み是正"),

    # ---- P3.5-2: 一般語トラップ（役職・一般語の誤検出除外）----
    ("trap_role_01", "trap-role",
     "ご担当者様、お世話になっております。", [], "担当者は人名でない"),
    ("trap_role_02", "trap-role",
     "関係者各位、下記の通りご連絡いたします。", [], "関係者/各位"),

    # ---- P3.5-3: 複合語トラップ（同一表記伝播の境界ガード）----
    # 敬称付きの1つ目だけが人名。2つ目は複合語内部（区役所/魂）で伝播禁止。
    ("compound_trap_01", "compound-trap",
     "青葉様より、青葉区役所への申請書を確認しました。",
     [ent("青葉", P, nth=0)], "青葉区役所へ伝播しない"),
    ("compound_trap_02", "compound-trap",
     "大和様の発表資料です。大和魂という表現は避けてください。",
     [ent("大和", P, nth=0)], "大和魂へ伝播しない"),

    # ---- P6: 未知固有名詞（法人格なし・辞書外）。決定的層は取りこぼす想定。
    #        LLM 検証パス on/off の recall 差測定用（§7）。
    ("unknown_org_01", "unknown-entity",
     "先日、オリオン企画と新規の取引基本契約を締結しました。",
     [ent("オリオン企画", O)], "未知組織・法人格なし・辞書外"),
    ("unknown_org_02", "unknown-entity",
     "今回の見積の窓口はネビュラ物流になる見込みです。",
     [ent("ネビュラ物流", O)], "未知組織・法人格なし・辞書外"),

    # ---- 伝播の全角バリアント（原文座標 raw 比較で漏れていた回帰）----
    ("prop_fullwidth_01", "propagation-variant",
     "ACME株式会社と契約。追ってＡＣＭＥから請求書が届く。",
     [ent("ACME株式会社", O), ent("ＡＣＭＥ", O)], "NFKC影で全角ＡＣＭＥへ伝播"),

    # ---- P7: 住所エンティティ（郵便番号＋都道府県起点の住所）----
    ("address_01", "address",
     "郵便物は〒150-0001 東京都渋谷区神宮前一丁目2番3号までお願いします。",
     [ent("〒150-0001", A), ent("東京都渋谷区神宮前一丁目2番3号", A)], "郵便番号＋住所"),
    ("address_02", "address",
     "本社は大阪府大阪市北区梅田3-1-1にあります。",
     [ent("大阪府大阪市北区梅田3-1-1", A)], "都道府県起点住所"),
    # NFKC 非吸収のハイフン類（U+2212 −）を郵便番号・番地の両方で使う回帰ケース。
    ("address_03", "address",
     "移転先は〒530−0001 大阪府大阪市北区梅田3−1−1です。",
     [ent("〒530−0001", A), ent("大阪府大阪市北区梅田3−1−1", A)],
     "U+2212 マイナス区切りの郵便番号＋番地"),

    # ---- コア名伝播: 法人格付き初出 → 法人格なし再言及（辞書外）----
    # 辞書に載らない相手が「株式会社◯◯ … ◯◯」と再言及される実務最頻ケース。
    # 構造検出済み ORG のコア名を伝播で拾えることを回帰検知する。
    ("core_prop_01", "core-propagation",
     "本日、株式会社ハヤブサ企画の件で打合せしました。ハヤブサ企画の担当者は不在でした。",
     [ent("株式会社ハヤブサ企画", O), ent("ハヤブサ企画", O, nth=1)],
     "前置法人格→コア名再言及（辞書外）"),
    ("core_prop_02", "core-propagation",
     "ミナヅキ工業株式会社と基本契約を締結。以後の窓口はミナヅキ工業になります。",
     [ent("ミナヅキ工業株式会社", O), ent("ミナヅキ工業", O, nth=1)],
     "後置法人格→コア名再言及（辞書外）"),
    # コア名が複合語内部に現れる場合は伝播しない（境界ガードの回帰・P3.5-3 と同型）。
    ("core_prop_trap_01", "core-propagation",
     "株式会社ハクバ商事にご連絡ください。会場はハクバ商事ビルの3階です。",
     [ent("株式会社ハクバ商事", O)],
     "コア名は複合語（◯◯ビル）内部へ伝播しない"),
]


def _build_long_case() -> tuple:
    # 数千文字の長文ケース（同一表記の一貫性・性能の両方を確認）。
    block = (
        "株式会社アオヤマ商事の山田様より、(株)キリシマ電機の見積についてご連絡をいただきました。"
        "担当の佐藤課長と03-1234-5678で調整し、yamada@aoyama-example.co.jpに返信しました。"
    )
    text = ("これは長文の業務メールを想定したテストケースです。\n" + block + "\n") * 25
    entities = [
        ent("株式会社アオヤマ商事", O), ent("山田", P), ent("(株)キリシマ電機", O),
        ent("佐藤", P), ent("03-1234-5678", H), ent("yamada@aoyama-example.co.jp", E),
    ]
    return ("edge_long", "edge", text, entities, "数千文字長文")


CASES.append(_build_long_case())


def validate_and_dump() -> None:
    out = []
    seen_ids: set[str] = set()
    for cid, category, text, entities, note in CASES:
        assert cid not in seen_ids, f"duplicate id: {cid}"
        seen_ids.add(cid)
        for e in entities:
            assert e["surface"] in text, (
                f"[{cid}] surface {e['surface']!r} not found in text"
            )
            assert e["type"] in (P, O, L, A, E, H, M), f"[{cid}] bad type {e['type']}"
            if "nth" in e:
                occ = text.count(e["surface"])
                assert e["nth"] < occ, (
                    f"[{cid}] nth={e['nth']} out of range (only {occ} occurrences "
                    f"of {e['surface']!r})"
                )
        out.append({
            "id": cid,
            "category": category,
            "text": text,
            "entities": entities,
            "note": note,
        })

    dest = Path(__file__).with_name("corpus.json")
    dest.write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(out)} cases -> {dest}")


if __name__ == "__main__":
    validate_and_dump()
