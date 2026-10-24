"""Apply the visually checked 47r1 diagram/body reconstruction once."""

import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nist_translater.translation import audit_translations  # noqa: E402
from nist_translater.pdf_parser import parse_pdf_document  # noqa: E402

PAGES = {19, 20, 31, 34, 38}
TRANSLATIONS = {
    "pdf-p0031-b0004": "図4：情報交換の確立フェーズ",
    "pdf-p0031-b0005": "3.2.1 ステップ1：実装計画の策定",
    "pdf-p0031-b0006": "情報が安全に交換されるよう、共同計画チームは情報交換の実装計画を策定する。実装計画の目的は、情報交換の取り組みのあらゆる側面を1つの文書に集約し、合意文書で規定された技術要件をどのように実装するかを明確にすることである。十分に策定された実装計画は、情報交換を正常かつ安全に実装できる可能性を大きく高める。",
    "pdf-p0031-b0007": "必要に応じて、実装計画では次の事項を扱う。",
    "pdf-p0031-b0008": "情報交換に関与するシステムを記述する",
    "pdf-p0031-b0009": "交換する情報<sup>9</sup>の影響度レベルを特定する",
    "pdf-p0031-b0012": "交換する情報の機密性、完全性、および可用性を保護するために実装するセキュリティ管理策を特定し、記述する",
    "pdf-p0034-b0005": "ユーザーアカウントを管理する",
    "pdf-p0034-b0006": "セキュリティ評価と継続的認可を実施する。",
    "pdf-p0034-b0007": "イベントログを分析する。",
    "pdf-p0034-b0008": "セキュリティインシデントを報告し、対応する。",
    "pdf-p0034-b0009": "コンティンジェンシー計画の活動を調整する。",
    "pdf-p0034-b0010": "変更を管理する。",
    "pdf-p0034-b0011": "システムセキュリティ計画と適用される合意文書をレビューし、更新する。",
    "pdf-p0034-b0012": "情報交換を継続する必要性をレビューする。",
    "pdf-p0034-b0014": "図5：情報交換の維持フェーズ",
    "pdf-p0034-b0015": "3.3.1 明確な連絡経路の維持",
    "pdf-p0038-b0002": "本節では、図6に示す情報交換の終了プロセスを説明する。システムの中断を避けるため、可能な限り、情報交換は秩序立てた方法で終了する。",
    "pdf-p0038-b0004": "図6：情報交換の終了フェーズ",
    "pdf-p0038-b0005": "3.4.1 計画的な終了",
    "pdf-p0038-b0006": "情報交換を終了する決定には、適切な管理担当者、セキュリティ担当者、および技術担当者が関与し、1つ以上の参加組織でセキュリティ上の不備が続いていることや、情報交換を継続するミッション上の必要性がないことなど、妥当な理由に基づいて判断する。情報交換を終了する前に、終了を開始する側は他の当事者に書面で通知し、確認応答を受け取るまで待つ。通知には、情報交換を終了する理由、終了までの予定日程、および終了を実施する技術担当者と管理担当者を記載する。",
    "pdf-p0038-b0007": "組織が情報交換を終了する理由には、次のようなさまざまなものがある。",
}
FIGURES = {
    19: "図2：情報交換管理の計画・確立・維持・終了フェーズと、各フェーズ間の流れ。",
    20: "図3：共同計画チームの設置から情報交換の承認または拒否までの計画フェーズの6ステップ。",
    31: "図4：実装計画の策定、実行、情報交換の有効化からなる確立フェーズ。",
    34: "図5：情報交換の維持活動と、継続の必要性をレビューして継続または終了を選ぶ流れ。",
    38: "図6：計画的または緊急に情報交換を終了し、再開する場合は計画または確立フェーズの適切なステップに戻る流れ。",
}


def main():
    path = ROOT / "data/sp800-47r1-trans.json"
    document = json.loads(path.read_text())
    assert not document.get("source_repairs"), "Already applied"
    candidate = parse_pdf_document(
        ROOT / "data/sp800-47r1.pdf", document["number"], document["source_url"],
        pages=[19, 20, 31, 32, 34, 35, 38],
        asset_dir=ROOT / "html/assets/47r1", asset_prefix="assets/47r1")
    sha = hashlib.sha256((ROOT / "data/sp800-47r1.pdf").read_bytes()).hexdigest()
    assert sha == candidate["source_sha256"] == "3ba5248bab614da212440a1bcfe814f0068ef95ebc2d73025742bc78a89c865a"
    old = document["contents"]
    removed = [b for b in old if b["source_page"] in PAGES or b["id"] == "pdf-p0032-b0001"]
    repaired = []
    for block in candidate["contents"]:
        if block["source_page"] not in PAGES:
            continue
        block = deepcopy(block)
        original_id = block["id"]
        if original_id == "pdf-p0031-b0009":
            block["html"] = block["html"].replace("information9", "information<sup>9</sup>")
        matches = [b for b in old if b["source_page"] == block["source_page"] and
                   b["kind"] == block["kind"] and b["html"] == block["html"]]
        if block["kind"] == "figure":
            from bs4 import BeautifulSoup
            img = BeautifulSoup(block["html"], "html.parser").img
            block["html_ja"] = '<img src="%s" alt="%s">' % (img["src"], FIGURES[block["source_page"]])
        elif original_id in TRANSLATIONS:
            block["html_ja"] = TRANSLATIONS[original_id]
        else:
            assert len(matches) == 1 and matches[0]["html_ja"], original_id
            block["html_ja"] = matches[0]["html_ja"]
        block["id"] = original_id.replace("-b", "-e")
        block["source_hash"] = hashlib.sha256((block["kind"] + "\n" + block["html"] + "\n" +
                                                block.get("source_image_hash", "")).encode()).hexdigest()[:16]
        block["status"] = "draft"
        block["extraction_status"] = "verified"
        block["extraction_check"] = "visual-page"
        block["source_repair_check"] = {
            "document": "SP 800-47 Rev. 1", "pdf_sha256": sha, "dpi": 150,
            "pages": sorted({r["page"] for r in block["source_refs"]}),
            "source_hash": block["source_hash"],
            "note": "図・キャプション・本文を原本画像と照合。31ページから32ページ、34ページから35ページへの続きも確認。"}
        repaired.append(block)
    assert len(repaired) == 51
    removed_ids = {b["id"] for b in removed}
    document["contents"] = sorted([b for b in old if b["id"] not in removed_ids] + repaired,
                                   key=lambda b: (b["source_page"], b["source_refs"][0]["bbox"][1],
                                                  b["source_refs"][0]["bbox"][0]))
    document["source_repairs"] = {"source_sha256": sha, "pages": sorted(PAGES), "block_ids": [],
                                   "original_blocks": removed, "method": "reviewed-figure-and-body-reconstruction"}
    document["pdf_font_repairs"] = candidate["pdf_font_repairs"]
    audit_translations(document)
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")
    print("47r1: reconstructed", len(repaired), "blocks; archived", len(removed), "records; translations draft")


if __name__ == "__main__":
    main()
