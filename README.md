# NIST SP 800-63-4 英日対訳サイト

NIST SP 800 資料を段落単位に分解し、原文と日本語訳を並べた静的ページを生成します。SP 800-63 Revision 4 の4巻に加え、PDFで公開されている資料も取り込めます。

NIST の正式版PDFを要件確認の基準にしてください。このサイトは非公式の閲覧用資料で、NIST および米国商務省が作成・承認・推奨したものではありません。

NIST のロゴと米国商務省の紋章は、商標・公的標章として使用が制限されています。原本の表紙などから抽出された標章の画像は `reports/official-marks.json` に登録し、`python scripts/withhold_marks.py reports/official-marks.json` で公開ページから外します（ブロックには `official_mark` を付け、画像の代わりに注記を表示します）。「NIST 公式翻訳」「NIST が承認・推奨」と受け取られる表現は使いません。

| 巻 | 内容 | 生成ページ |
| --- | --- | --- |
| SP 800-63-4 | Digital Identity Guidelines | `html/sp800-63.html` |
| SP 800-63A-4 | Identity Proofing & Enrollment | `html/sp800-63a.html` |
| SP 800-63B-4 | Authentication & Authenticator Management | `html/sp800-63b.html` |
| SP 800-63C-4 | Federation & Assertions | `html/sp800-63c.html` |
| SP 800-18 Rev. 2 | Developing Security, Privacy, and Cybersecurity Supply Chain Risk Management Plans for Systems（PDF 原文抽出） | `html/sp800-18r2.html` |
| SP 800-92 | Guide to Computer Security Log Management（PDF 原文抽出・翻訳中） | `html/sp800-92.html` |
| SP 800-98 | Guidelines for Securing Radio Frequency Identification (RFID) Systems（PDF 原文抽出・翻訳中） | `html/sp800-98.html` |
| SP 800-101 Rev. 1 | Guidelines on Mobile Device Forensics（PDF 原文抽出・翻訳中） | `html/sp800-101r1.html` |
| SP 800-119 | Guidelines for the Secure Deployment of IPv6（PDF 原文抽出・翻訳中） | `html/sp800-119.html` |
| SP 800-122 | Guide to Protecting the Confidentiality of Personally Identifiable Information (PII)（PDF 原文抽出・翻訳中） | `html/sp800-122.html` |
| SP 800-123 | Guide to General Server Security（PDF 原文抽出・翻訳中） | `html/sp800-123.html` |
| SP 800-121 Rev. 2 | Guide to Bluetooth Security（2022年1月更新を含むPDF原文抽出・翻訳中） | `html/sp800-121r2.html` |
| SP 800-125 | Guide to Security for Full Virtualization Technologies（PDF 原文抽出・翻訳中） | `html/sp800-125.html` |
| SP 800-125A Rev. 1 | Security Recommendations for Server-based Hypervisor Platforms（PDF 原文抽出・翻訳中） | `html/sp800-125ar1.html` |
| SP 800-125B | Secure Virtual Network Configuration for Virtual Machine (VM) Protection（PDF 原文抽出・翻訳済みドラフト、図4件は原文保持） | `html/sp800-125b.html` |
| SP 800-171 Rev. 3 | Protecting Controlled Unclassified Information in Nonfederal Systems and Organizations（NIST 公式 HTML 原文） | `html/sp800-171r3.html` |
| SP 800-126 Rev. 4 | Technical Specification for the Security Content Automation Protocol (SCAP): SCAP Version 1.4（PDF 原文抽出） | `html/sp800-126r4.html` |
| SP 800-126A Rev. 4 | SCAP 1.4 Component Specification Version Updates: An Annex to NIST SP 800-126r4（PDF 原文抽出） | `html/sp800-126ar4.html` |
| SP 800-172 Rev. 3 | Enhanced Security Requirements for Protecting Controlled Unclassified Information（PDF 原文抽出） | `html/sp800-172r3.html` |
| SP 800-172A Rev. 3 | Assessing Enhanced Security Requirements for Controlled Unclassified Information（PDF 原文抽出） | `html/sp800-172ar3.html` |
| SP 800-70 Rev. 5 | National Checklist Program for IT Products: Guidelines for Checklist Users and Developers（PDF 原文抽出） | `html/sp800-70r5.html` |
| SP 800-81 Rev. 3 | Secure Domain Name System (DNS) Deployment Guide（PDF 原文抽出） | `html/sp800-81r3.html` |
| SP 800-88 Rev. 2 | Guidelines for Media Sanitization（PDF 原文抽出） | `html/sp800-88r2.html` |
| SP 800-61 Rev. 3 | Incident Response Recommendations and Considerations for Cybersecurity Risk Management: A CSF 2.0 Community Profile（PDF 原文抽出） | `html/sp800-61r3.html` |
| SP 800-66 Rev. 2 | Implementing the Health Insurance Portability and Accountability Act (HIPAA) Security Rule: A Cybersecurity Resource Guide（PDF 原文抽出） | `html/sp800-66r2.html` |
| SP 800-216 | Recommendations for Federal Vulnerability Disclosure Guidelines（PDF 原文抽出） | `html/sp800-216.html` |
| SP 800-220 | Fiscal Year 2021 Cybersecurity and Privacy Annual Report（PDF 原文抽出） | `html/sp800-220.html` |
| SP 800-225 | Fiscal Year 2022 Cybersecurity and Privacy Annual Report（PDF 原文抽出） | `html/sp800-225.html` |
| SP 800-219 Rev. 1 | Automated Secure Configuration Guidance from the macOS Security Compliance Project (mSCP)（PDF 原文抽出） | `html/sp800-219r1.html` |
| SP 800-215 | Guide to a Secure Enterprise Network Landscape（PDF 原文抽出） | `html/sp800-215.html` |
| SP 800-204C | Implementation of DevSecOps for a Microservices-based Application with Service Mesh（PDF 原文抽出） | `html/sp800-204c.html` |
| SP 800-204A | Building Secure Microservices-based Applications Using Service-Mesh Architecture（PDF 原文抽出） | `html/sp800-204a.html` |
| SP 800-204 | Security Strategies for Microservices-based Application Systems（PDF 原文抽出） | `html/sp800-204.html` |
| SP 800-203 | 2017 NIST/ITL Cybersecurity Program Annual Report（PDF 原文抽出・翻訳中） | `html/sp800-203.html` |
| SP 800-202 | Quick Start Guide for Populating Mobile Test Devices（PDF 原文抽出） | `html/sp800-202.html` |
| SP 800-193 | Platform Firmware Resiliency Guidelines（PDF 原文抽出） | `html/sp800-193.html` |
| SP 800-195 | 2016 NIST/ITL Cybersecurity Program Annual Report（PDF 原文抽出・翻訳中） | `html/sp800-195.html` |
| SP 800-192 | Verification and Test Methods for Access Control Policies/Models（PDF 原文抽出） | `html/sp800-192.html` |
| SP 800-190 | Application Container Security Guide（PDF 原文抽出） | `html/sp800-190.html` |
| SP 800-189 | Resilient Interdomain Traffic Exchange: BGP Security and DDoS Mitigation（PDF 原文抽出） | `html/sp800-189.html` |
| SP 800-188 | De-Identifying Government Datasets: Techniques and Governance（PDF 原文抽出） | `html/sp800-188.html` |
| SP 800-181 Rev. 1 | Workforce Framework for Cybersecurity (NICE Framework)（PDF 原文抽出・翻訳前） | `html/sp800-181r1.html`（未生成） |
| SP 800-182 | Computer Security Division 2015 Annual Report（PDF 原文抽出） | `html/sp800-182.html` |
| SP 800-168 | Approximate Matching: Definition and Terminology（PDF 原文抽出・翻訳済みドラフト） | `html/sp800-168.html` |
| SP 800-167 | Guide to Application Whitelisting（PDF 原文抽出・翻訳中） | `html/sp800-167.html` |
| SP 800-166 | Derived PIV Application and Data Model Test Guidelines（PDF 原文抽出・翻訳済みドラフト） | `html/sp800-166.html` |
| SP 800-165 | Computer Security Division 2012 Annual Report（PDF 原文抽出・ドラフト翻訳完了） | `html/sp800-165.html` |
| SP 800-163 Rev. 1 | Vetting the Security of Mobile Applications（PDF 原文抽出・ドラフト翻訳完了：576/584ブロック、図版8ブロックは原文保持） | `html/sp800-163r1.html` |
| SP 800-162 | Guide to Attribute Based Access Control (ABAC) Definition and Considerations（PDF 原文抽出・ドラフト翻訳完了：462/482ブロック、図版20ブロックは原文保持） | `html/sp800-162.html` |
| SP 800-176 | Computer Security Division 2014 Annual Report（PDF 原文抽出・翻訳中） | `html/sp800-176.html` |
| SP 800-183 | Networks of 'Things'（PDF 原文抽出・翻訳済みドラフト） | `html/sp800-183.html` |
| SP 800-184 | Guide for Cybersecurity Event Recovery（PDF 原文抽出・翻訳済みドラフト） | `html/sp800-184.html` |
| SP 800-145 | The NIST Definition of Cloud Computing（PDF 原文抽出・翻訳済みドラフト） | `html/sp800-145.html` |
| SP 800-146 | Cloud Computing Synopsis and Recommendations（PDF 原文抽出・949/967ブロック翻訳済み、18ブロック原文保持） | `html/sp800-146.html` |
| SP 800-147 | BIOS Protection Guidelines（PDF 原文抽出・翻訳済みドラフト） | `html/sp800-147.html` |
| SP 800-147B | BIOS Protection Guidelines for Servers（PDF 原文抽出・ドラフト翻訳完了：387/428ブロック、図版・参考文献41ブロックは原文保持） | `html/sp800-147b.html` |
| SP 800-150 | Guide to Cyber Threat Information Sharing（PDF 原文抽出・翻訳済みドラフト） | `html/sp800-150.html` |
| SP 800-152 | A Profile for U.S. Federal Cryptographic Key Management Systems (CKMS)（PDF 原文抽出・ドラフト翻訳完了：1,315/1,318ブロック、図版3ブロックは原文保持） | `html/sp800-152.html` |
| SP 800-153 | Guidelines for Securing Wireless Local Area Networks (WLANs)（PDF 原文抽出・ドラフト翻訳完了：255/256ブロック、図版1ブロックは原文保持） | `html/sp800-153.html` |
| SP 800-156 | Representation of PIV Chain-of-Trust for Import and Export（PDF 原文抽出・ドラフト翻訳完了：429/454ブロック、図版・XMLスキーマ等25ブロックは原文保持） | `html/sp800-156.html` |
| SP 800-157 | Guidelines for Derived Personal Identity Verification (PIV) Credentials（PDF 原文抽出・ドラフト翻訳完了：471/474ブロック、図版3ブロックは原文保持） | `html/sp800-157.html` |
| SP 800-185 | SHA-3 Derived Functions: cSHAKE, KMAC, TupleHash, and ParallelHash（PDF 原文抽出・翻訳前） | `html/sp800-185.html`（未生成） |
| SP 800-187 | Guide to LTE Security（PDF 原文抽出） | `html/sp800-187.html` |
| SP 800-186 | Recommendations for Discrete Logarithm-based Cryptography: Elliptic Curve Domain Parameters（PDF 原文抽出） | `html/sp800-186.html` |
| SP 800-204B | Attribute-based Access Control for Microservices-based Applications using a Service Mesh（PDF 原文抽出） | `html/sp800-204b.html` |
| SP 800-213 | IoT Device Cybersecurity Guidance for the Federal Government: Establishing IoT Device Cybersecurity Requirements（PDF 原文抽出） | `html/sp800-213.html` |
| SP 800-213A | IoT Device Cybersecurity Guidance for the Federal Government: IoT Device Cybersecurity Requirement Catalog（PDF 原文抽出） | `html/sp800-213a.html` |
| SP 800-207A | A Zero Trust Architecture Model for Access Control in Cloud-Native Applications in Multi-Cloud Environments（PDF 原文抽出） | `html/sp800-207a.html` |
| SP 800-207 | Zero Trust Architecture（PDF 原文抽出） | `html/sp800-207.html` |
| SP 800-214 | 2020 Cybersecurity and Privacy Annual Report（PDF 原文抽出） | `html/sp800-214.html` |
| SP 800-211 | 2019 NIST/ITL Cybersecurity Program Annual Report（PDF 原文抽出） | `html/sp800-211.html` |
| SP 800-210 | General Access Control Guidance for Cloud Systems（PDF 原文抽出） | `html/sp800-210.html` |
| SP 800-209 | Security Guidelines for Storage Infrastructure（PDF 原文抽出） | `html/sp800-209.html` |
| SP 800-208 | Recommendation for Stateful Hash-Based Signature Schemes（PDF 原文抽出） | `html/sp800-208.html` |
| SP 800-206 | Annual Report 2018: NIST/ITL Cybersecurity Program（PDF 原文抽出） | `html/sp800-206.html` |
| SP 800-205 | Attribute Considerations for Access Control Systems（PDF 原文抽出） | `html/sp800-205.html` |
| SP 800-90C | Recommendation for Random Bit Generator (RBG) Constructions（PDF 原文抽出） | `html/sp800-90c.html` |
| SP 800-227 | Recommendations for Key-Encapsulation Mechanisms（PDF 原文抽出） | `html/sp800-227.html` |
| SP 800-223 | High-Performance Computing Security: Architecture, Threat Analysis, and Security Posture（PDF 原文抽出） | `html/sp800-223.html` |
| SP 800-226 | Guidelines for Evaluating Differential Privacy Guarantees（PDF 原文抽出） | `html/sp800-226.html` |
| SP 800-221 | Enterprise Impact of Information and Communications Technology Risk: Governing and Managing ICT Risk Programs Within an Enterprise Risk Portfolio（PDF 原文抽出） | `html/sp800-221.html` |
| SP 800-221A | Information and Communications Technology (ICT) Risk Outcomes: Integrating ICT Risk Management Programs with the Enterprise Risk Portfolio（PDF 原文抽出） | `html/sp800-221a.html` |
| SP 800-218A | Secure Software Development Practices for Generative AI and Dual-Use Foundation Models: An SSDF Community Profile（PDF 原文抽出） | `html/sp800-218a.html` |
| SP 800-218 | Secure Software Development Framework (SSDF) Version 1.1: Recommendations for Mitigating the Risk of Software Vulnerabilities（PDF 原文抽出） | `html/sp800-218.html` |
| SP 800-201 | NIST Cloud Computing Forensic Reference Architecture（PDF 原文抽出） | `html/sp800-201.html` |
| SP 800-55 Vol. 2 | Measurement Guide for Information Security: Volume 2 — Developing an Information Security Measurement Program（PDF 原文抽出） | `html/sp800-55v2.html` |
| SP 800-55 Vol. 1 | Measurement Guide for Information Security: Volume 1 — Identifying and Selecting Measures（PDF 原文抽出） | `html/sp800-55v1.html` |
| SP 800-144 | Guidelines on Security and Privacy in Public Cloud Computing（PDF 原文抽出・翻訳完了：471/984ブロック、参考文献・図表513ブロック原文保持） | `html/sp800-144.html` |
| SP 800-142 | Practical Combinatorial Testing（PDF 原文抽出・ドラフト翻訳完了：666/977ブロック、図表・抽出崩れ・参考文献311ブロック原文保持） | `html/sp800-142.html` |
| SP 800-111 | Guide to Storage Encryption Technologies for End User Devices（PDF 原文抽出・ドラフト翻訳完了：434/437ブロック、図版3ブロック原文保持） | `html/sp800-111.html` |
| SP 800-161 Rev. 1 (Update 1) | Cybersecurity Supply Chain Risk Management Practices for Systems and Organizations（PDF 原文抽出） | `html/sp800-161r1upd1.html` |
| SP 800-35 | Guide to Information Technology Security Services（PDF 原文抽出・翻訳完了：1030/1049ブロック、19ブロック原文保持） | `html/sp800-35.html` |
| SP 800-49 | Federal S/MIME V3 Client Profile（PDF 原文抽出・ドラフト翻訳完了：401/402ブロック、図版1ブロックは原文保持） | `html/sp800-49.html` |
| SP 800-50 Rev. 1 | Building a Cybersecurity and Privacy Learning Program（PDF 原文抽出） | `html/sp800-50r1.html` |
| SP 800-204D | Strategies for the Integration of Software Supply Chain Security in DevSecOps CI/CD Pipelines（PDF 原文抽出） | `html/sp800-204d.html` |
| SP 800-108 Rev. 1 (Update 1) | Recommendation for Key Derivation Using Pseudorandom Functions（PDF 原文抽出） | `html/sp800-108r1upd1.html` |
| SP 800-228 (Update 1) | Guidelines for API Protection for Cloud-Native Systems（PDF 原文抽出） | `html/sp800-228upd1.html` |
| SP 800-131A Rev. 2 | Cryptographic Algorithms and Key Lengths（PDF 原文抽出） | `html/sp800-131ar2.html` |
| SP 800-132 | Recommendation for Password-Based Key Derivation: Part 1: Storage Applications（PDF 原文抽出・改訂予定・翻訳前） | `html/sp800-132.html` |
| SP 800-238 | Fiscal Year 2025 Annual Report for NIST Cybersecurity and Privacy Program（PDF 原文抽出） | `html/sp800-238.html` |
| SP 800-236 | Fiscal Year 2024 Annual Report for NIST Cybersecurity and Privacy Program（PDF 原文抽出） | `html/sp800-236.html` |
| SP 800-234 | High-Performance Computing (HPC) Security Overlay（PDF 原文抽出） | `html/sp800-234.html` |
| SP 800-233 | Service Mesh Proxy Models for Cloud-Native Applications（PDF 原文抽出） | `html/sp800-233.html` |
| SP 800-232 | Ascon-Based Lightweight Cryptography Standards for Constrained Devices（PDF 原文抽出） | `html/sp800-232.html` |
| SP 800-231 | Bug Framework (BF): Formalizing Cybersecurity Weaknesses and Vulnerabilities（PDF 原文抽出） | `html/sp800-231.html` |
| SP 800-229 | Fiscal Year 2023 Cybersecurity and Privacy Annual Report（PDF 原文抽出） | `html/sp800-229.html` |

## セットアップと生成

Python 3.10 以降を使用します。PDF 抽出の動作確認には Python 3.11 を使用しました。

```sh
python3.11 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python3 main.py update --document 63a
python3 -m http.server 8000 --directory html
```

`--document` には `63`、`63a`、`63b`、`63c`、`18r2`、`66r2`、`87r2`、`125`、`125ar1`、`125b`、`126r4`、`126ar4`、`126r2`、`126a`、`126r1`、`171r3`、`172r3`、`172ar3`、`70r5`、`81r3`、`228upd1`、`88r2`、`90c`、`61r3`、`201`、`55v2`、`55v1`、`50r1`、`49`、`35`、`204d`、`204c`、`204b`、`204a`、`204`、`203`、`202`、`193`、`192`、`190`、`189`、`188`、`187`、`186`、`184`、`108r1upd1`、`227`、`226`、`225`、`223`、`221`、`221a`、`218a`、`218`、`216`、`220`、`219r1`、`215`、`213`、`213a`、`207a`、`214`、`211`、`210`、`209`、`208`、`207`、`206`、`205`、`131ar2`、`170`、`168`、`167`、`166`、`165`、`163r1`、`162`、`157`、`156`、`145`、`144`、`142`、`146`、`147`、`147b`、`150`、`152`、`153`、`238`、`236`、`234`、`233`、`232`、`231`、`229`、`111`、`161r1upd1` を指定します。省略時は従来どおり `63b` です。`update` はNISTから原文を取得し、JSONを作成または更新してHTMLを出力します。各処理は個別にも実行できます。

```sh
python3 main.py fetch --document 63c
python3 main.py parse --document 63c
python3 main.py build --document 63c
```

HTMLは `http://localhost:8000/sp800-63c.html` で確認できます。`fetch` / `update` で原文を取得する場合はネット接続が必要です。取得した HTML は解析成功後に削除されます。

## 現行 Final 資料一覧

`https://csrc.nist.gov/publications/sp800` の現行一覧から、系列が SP、番号が 800 系、ステータスが Final のレコードを抽出します。スナップショットは `data/sp800-final-catalog.json` に保存し、翻訳データがある資料は進捗とJSON/HTMLのパスも記録します。2026年9月26日時点の一覧は195件です。

```sh
python3 scripts/update_sp800_final_catalog.py
```

再取得にはネット接続が必要です。NISTが一覧を更新した後に実行すると、台帳も最新化されます。

## 対訳一覧ページ

**html/index.html** は現行 Final 資料の一覧です。資料番号・英日タイトルで検索し、対訳ページの有無と翻訳状態で絞り込めます。検索は全角数字や `SP800-53` などの表記にも対応し、空白で区切った語をすべて含む資料を表示します。資料番号とタイトルから対訳へ移動でき、資料番号順・刊行日順で並べ替えられます。検索条件はURLと同じタブのセッションに保存され、資料から戻った際にも維持されます。スマートフォンでは資料ごとの縦型表示になります。

「訳文作成済み」は登録された翻訳対象ブロックに訳文が揃った状態で、未レビュー訳を含みます。「訳文レビュー済み」はその訳文がすべてレビュー済みの状態です。図表・参考文献等の「原文保持」、PDF抽出の照合待ち、一部収録は別に表示します。進捗バーは登録ブロック全体に対する日本語訳の割合で、原文保持分を含めません。状態と内訳は、生成時に各翻訳JSONから再集計します。

一覧だけを生成する場合:

    python3 scripts/build_translation_index.py

各資料のHTML生成時と、現行Final資料カタログの更新時にも一覧を自動で再生成します。コマンドから単独実行する場合は **python3 main.py index** を使います。


## SP 800-22r1 の数式修正

本文の数式はKaTeXで表示し、図と図中の数式は原本画像で保持します。数式を含む表は画像にせず、意味と構造を表すLaTeXとHTMLの表に復元します。文字座標の再現は行いません。KaTeX 0.18.9とフォントはサイト内に同梱しています。

```sh
python3 scripts/repair_sp800_22_math.py
```

`parse --document 22r1`でも同じ修正を適用します。修正対象のPDFはSHA-256で固定しています。原本が変わった場合は、図の領域と数式を再確認するまで適用しません。

数式の修正は`data/sp800-22r1-trans.json`内の各ブロックに保存します。`html`と`html_ja`の両方にKaTeX用のLaTeXを`\(...\)`または`\[...\]`で記載し、別の数式JSONは使いません。再抽出時もこの英日文を引き継ぎ、`math_source_hashes`で対応する抽出原文の変更を検知します。CSS・JavaScript・フォント・ライセンスは`static/vendor/katex/`から`html/vendor/katex/`へコピーし、HTMLはローカルファイルを参照します。

全333領域を通常のLaTeXとして保存し、原本と修正後のChrome表示を比較しました。全領域に現在の原文HTMLに対応する比較記録があります。確認範囲と原本の不整合は[数式レビュー記録](reports/sp800-22-math-review.md)に記載します。表示・構文の検証は原本との完全な照合を意味しないため、未確認の抽出状態は`needs_review`を維持します。この273領域の`html_ja`にも同じ数式を保存しますが、説明文の訳は再確認待ちで、翻訳状態は`untranslated`のままです。崩れた抽出文に基づく旧訳は`math_preservation.original_blocks`に保存し、再抽出時にも引き継ぎます。原本の計算・表記の不整合は`math_review_notes`に記録します。

抽出・翻訳のルールは[資料抽出・翻訳スキル](skills/nist-document-extraction/SKILL.md)に定義し、[AGENTS.md](AGENTS.md)から参照します。`htmlStyle`、`mathrlap`、`vphantom`等による座標配置へのフォールバックを禁止し、曖昧な式は高解像度の原本、前後の記述、版を確認した公式情報を照合して復元します。

数式の検証は`python3 -m unittest discover -s tests -p test_pdf_math.py`で実行できます。Node.jsがあれば、保存した全KaTeX式の構文も同梱ライブラリで検証します。

## PDF だけの資料

`18r2`、`49`、`35`、`87r2`、`126r4`、`126ar4`、`126r2`、`126a`、`126r1`、`172r3`、`172ar3`、`70r5`、`81r3`、`88r2`、`228upd1`、`131ar2`、`170`、`168`、`167`、`166`、`165`、`163r1`、`162`、`157`、`156`、`145`、`142`、`146`、`147`、`147b`、`150`、`152`、`153`、`90c`、`61r3`、`227`、`226`、`223`、`221`、`221a`、`218a`、`201`、`55v2`、`204d`、`204c`、`204b`、`204a`、`204`、`203`、`202`、`193`、`192`、`190`、`188`、`187`、`186`、`184`、`219r1`、`215`、`213`、`213a`、`207a`、`214`、`211`、`210`、`209`、`208`、`207`、`206`、`205`、`238`、`236`、`234`、`233`、`232`、`231`、`229`、`111`、`161r1upd1` は PDF 原本から抽出した資料です。訳文は `draft` で、PDF原文の抽出状態は `needs_review` です。表や図は HTML と原本から切り出した画像を併記します。図中の文字や複雑な表を含め、原文と照合してから抽出状態を `verified` にしてください。

```sh
python3 main.py fetch --document 131ar2
python3 main.py parse --document 131ar2
python3 main.py build --document 131ar2
```

`--pages` を省略すると PDF 全ページを抽出します。一部ページだけを確認するときは `--pages 7-8,15,21` を指定します。この場合、出力ページに未収録ページがある旨を表示します。新しい PDF 資料は `src/nist_translater/documents.py` に `source_format: "pdf"` と公式 PDF URL を登録します。PDF 原本は `data/*.pdf` に保持しますが、Git の対象外です。再取得しても訳文は同じ原文ブロックへ引き継がれ、変化したブロックは `stale` になります。

PDF ブロックには `source_page`、`source_refs`（原本中の座標）、`extraction_status` を記録します。抽出直後は `needs_review` です。原本と照合したブロックだけ `verified` に設定してください。訳文の `reviewed` は、原文抽出が `verified` の場合に限って受け付けます。画像だけの PDF は先に OCR で文字層を作り、`data/sp800-<slug>.pdf` に置いてから `parse` を実行します。`fetch` はそのファイルを公式 PDF で上書きします。

## 訳文の追加

### agy による自動翻訳

`agy` が使える環境では、指定した巻の未翻訳ブロックを翻訳できます。完了したバッチは該当する `data/sp800-63*-trans.json` に保存され、再実行すると未翻訳分から再開します。訳は `draft` です。

```sh
python3 main.py translate --document 63a
python3 main.py translate --document 63c --limit 30 --batch-size 8 --timeout 180
python3 main.py translate --document 63a --limit 0 --dry-run
```

既定では1回あたり最大8ブロック・英文5,000文字をまとめます。表のHTMLも翻訳入力に含まれます。全文実行前に `--dry-run` で呼び出し回数と対象量を確認してください。

翻訳依頼時はHTMLタグをプレースホルダーに置き換え、モデルが本文だけを翻訳できるようにしてから元のタグを復元します。返答のID・原文ハッシュ・件数・HTML構造・規範語を検証し、検証に通ったバッチだけを原子的に保存します。JSON検証が保証するのは構造と原文との対応です。訳の意味や規範表現の正確さは人手でレビューしてください。

### 手動で訳文を追加

各巻の `data/sp800-63*-trans.json` の対象要素を編集します。`html_ja` に訳文を入れ、`status` を `draft` または `reviewed` に設定してから、その巻のページを再生成します。

```sh
python3 main.py build --document 63a
```

各要素は原文 `html` と訳文 `html_ja` を持ちます。追加フィールドは `id`、`source_hash`、`status` です。原文が変化した要素は `status: "stale"` となり、公開ページでは旧訳を表示しません。図と脚注は原文を表示します。

## 構成

```text
main.py                    コマンド入口
src/nist_translater/       取得・構造化・訳文管理・ページ生成
data/sp800-*-trans.json    各巻の原文、訳文、原文ハッシュ、レビュー状態
templates/page.html        共通ページテンプレート
static/style.css           スタイル
html/                      生成ページ
tests/                     パーサーと訳文更新の検証
```

## 検証

```sh
python3 -m unittest discover -s tests
```

公開前には、原文・訳文と生成済みHTMLの置換文字「�」を横断検査します。残存があれば終了コード1になります。

```sh
.venv/bin/python scripts/audit_source_encoding.py --report reports/source-encoding-audit.json
```

置換文字を含む原文は翻訳対象から外し、照合済み・レビュー済みにはできません。ページ生成も拒否します。既知のPDFに対する文字変換・図領域の補正は原本のSHA-256に限定し、再抽出時にも正本JSON内の修復を保持します。原本の版が変わった場合は再確認が必要です。[修復範囲・再発防止の詳細](reports/source-encoding-repair.md)を参照してください。
