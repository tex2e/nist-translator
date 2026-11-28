# NIST IR の訳語（第 1 陣で決めたもの。全 IR 共通）

固定の訳語（translator-instructions.md）と、全資料共通の用語表 `data/glossary.json`（`scripts/check_glossary.py` が照合する）を最優先する。そのうえで、関連する既存の SP 800 の訳に合わせる。

- CSF の機能: 統治（GOVERN）・識別（IDENTIFY）・防御（PROTECT）・検知（DETECT）・対応（RESPOND）・復旧（RECOVER）。カテゴリ・サブカテゴリの識別子は英語のまま。Community Profile = コミュニティプロファイル、Organizational Profile = 組織プロファイル、Current/Target Profile = 現在のプロファイル／目標プロファイル、outcome = 成果。
- ERM 系（SP 800-221 に合わせる）: enterprise = エンタープライズ、risk register = リスク登録簿、risk appetite = リスク選好度、risk tolerance = リスク許容度、risk exposure = リスクエクスポージャー、business impact analysis = 事業影響分析（BIA）、risk detail record = リスク詳細記録（RDR）。
- IoT 系（SP 800-213 に合わせる）: securable = セキュリティ保護可能（な）、securability = セキュリティ保護可能性、manufacturer = 製造者。
- 認証系（SP 800-63 に合わせる）: authenticator = 認証器、subscriber = 加入者、claimant = 請求者、applicant = 申請者、relying party = 依拠当事者（RP）、federation = フェデレーション、assertion = アサーション、memorized secret = 記憶された秘密情報。
- 暗号: post-quantum = 耐量子、PQC = 耐量子暗号、RSA modulus = RSA 法、secret key（共通鍵の意味）= 共通鍵、private key = 秘密鍵。
- 書式: 序数の `4<sup>th</sup>` などはタグを保つため「4日（4<sup>th</sup>）」の形でよい。参考文献の "Available at" = 「入手先:」。
- 第 2 陣で統一したもの: nonce = ノンス（2026-11-28 に全資料でノンスへ統一）、mode of operation = 暗号利用モード（2026-11-28 に変更。システムの動作状態を指すものは動作モード）、tweak / tweakable / tweakey = tweak / tweak 可能な / tweakey（英語のまま）、Focal Document = フォーカル文書、Reference Document = 参照文書、Informative Reference = 参考情報、CSF のカテゴリ Awareness and Training = 意識向上およびトレーニング、Security Continuous Monitoring = セキュリティの継続的監視。
- 表紙裏の定型文 "For planning and transition purposes, federal agencies may wish to closely follow the development of these new publications by NIST." は「計画および移行のため、連邦機関は、NIST によるこれらの新しい刊行物の策定状況を注意深く追うことを検討してもよいです。」に統一。
- 第 3 陣で統一したもの: attestation = アテステーション（「構成証明」は使わない）、measured launch = 計測済み起動、trusted boot = トラステッドブート、root of trust = ルートオブトラスト、IoT のベースラインの capability = 能力（「サイバーセキュリティ能力」「非技術的支援能力」。sp800-213・ir-8259b に合わせる）、security awareness = セキュリティ意識向上、relying party = 依拠当事者、decapsulation = 脱カプセル化。
- provenance = 来歴（SP 800 の多数に合わせる）、pedigree = ペディグリー。
- 第 4 陣で統一したもの: Appendix = 付録（Annex = 附属書）、permissioned / permissionless = 許可型 / 非許可型、Applied Cybersecurity Division = 応用サイバーセキュリティ部門、threshold scheme = しきい値方式（ir-8214・8214a・8214c）。
- 第 10 陣で統一したもの: certification = 認証、accreditation = 認定（certification and accreditation = 認証および認定。SP 800-37 系の既存の訳に合わせる。「アクレディテーション」は使わない）、NBS = 米国標準局（NBS）、ICST = 計算機科学技術研究所（ICST）、NCSL = 国立コンピューターシステム研究所（NCSL）、discretionary access control = 任意アクセス制御（DAC）。
- 2026-11-28 に全資料で統一したもの（`data/glossary.json`）: 長音はつける（サーバー、ユーザー、インターフェース、パラメーター、コンピューター。ユーザビリティ・ユーザブルは別語）、stakeholder = 利害関係者（「ステークホルダー」は使わない）、root of trust = ルートオブトラスト（「信頼の基点」「信頼の起点」は使わない）、authenticator = 認証器、threat actor = 脅威アクター、mode of operation = 暗号利用モード（暗号のモード。システムの動作状態は動作モード）、trust anchor = トラストアンカー、post-quantum = 耐量子、sensitive = 機微（「機密」は classified・confidential・secret の訳に限る）。
