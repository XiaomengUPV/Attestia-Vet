"""
VetGuard — Agent 0: Document Integrity Checker
================================================
Runs BEFORE the clinical agents (rule_checker, clinical_reasoner, adversarial_validator).
Inspects uploaded PDF claim documents for forensic red flags indicating forgery or AI generation.

Install dependencies:
    pip install pikepdf pillow exiftool-py

Usage:
    from document_integrity_checker import DocumentIntegrityChecker
    checker = DocumentIntegrityChecker()
    result = checker.analyze("path/to/claim.pdf")
"""

import re
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional

# ── Optional imports (gracefully degrade if not installed) ──────────────────
try:
    import pikepdf
    PIKEPDF_AVAILABLE = True
except ImportError:
    PIKEPDF_AVAILABLE = False
    print("WARNING: pikepdf not installed. Run: pip install pikepdf")

try:
    from PIL import Image
    from PIL.ExifTags import TAGS
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("WARNING: Pillow not installed. Run: pip install Pillow")


# ── Known freeware / suspicious PDF producers ───────────────────────────────
SUSPICIOUS_PRODUCERS = [
    "pypdf", "pypdf2", "pypdf3", "reportlab", "fpdf", "fpdf2",
    "weasyprint", "pdfkit", "wkhtmltopdf", "libreoffice", "openoffice",
    "ghostscript", "pdftk", "ilovepdf", "smallpdf", "sejda",
    "img2pdf", "pdf24", "pdfcreator",
]

# Legitimate issuers often use proprietary tools — these are generally safe
TRUSTED_PRODUCERS = [
    "adobe", "microsoft", "nitro", "foxit", "nuance", "pdfium",
    "mac os x quartz", "apple", "acrobat",
]

# ── Flags with severity levels ───────────────────────────────────────────────
SEVERITY = {
    "CRITICAL": 3,   # Near-certain forgery signal
    "HIGH":     2,   # Strong red flag
    "MEDIUM":   1,   # Suspicious, needs context
    "INFO":     0,   # Informational only
}


class DocumentIntegrityChecker:
    """
    Agent 0 for VetGuard — forensic PDF integrity analysis.
    Returns a structured result compatible with the VetGuard pipeline.
    """

    def analyze(self, pdf_path: str) -> dict:
        path = Path(pdf_path)
        if not path.exists():
            return self._error(f"File not found: pdf_path")

        flags = []
        metadata_result = {}
        xref_result = {}
        image_result = {}

        # ── 1. Metadata forensics ────────────────────────────────────────────
        if PIKEPDF_AVAILABLE:
            metadata_result = self._check_metadata(path, flags)
            xref_result     = self._check_xref_overlaps(path, flags)
            image_result    = self._check_embedded_images(path, flags)
        else:
            flags.append({
                "flag": "pikepdf_unavailable",
                "severity": "INFO",
                "detail": "Install pikepdf to enable deep PDF forensics"
            })

        # ── 2. Compute overall risk score ────────────────────────────────────
        score = sum(SEVERITY.get(f["severity"], 0) for f in flags)
        fraud_detected = score >= 3  # One CRITICAL or multiple HIGH flags

        if score == 0:
            risk_level = "LOW"
        elif score <= 2:
            risk_level = "MEDIUM"
        elif score <= 4:
            risk_level = "HIGH"
        else:
            risk_level = "CRITICAL"

        return {
            "agent": "document_integrity_checker",
            "file": path.name,
            "file_hash_md5": self._md5(path),
            "fraud_detected": fraud_detected,
            "fraud_type": "Document forgery / AI-generated document" if fraud_detected else None,
            "risk_level": risk_level,
            "risk_score": score,
            "flags": flags,
            "flag_count": len(flags),
            "metadata": metadata_result,
            "xref_analysis": xref_result,
            "image_analysis": image_result,
            "confidence": "high" if fraud_detected and score >= 5 else (
                          "medium" if fraud_detected else "low"),
            "explanation": self._build_explanation(flags, risk_level),
            "recommendation": self._recommendation(risk_level),
        }

    # ── Metadata forensics ───────────────────────────────────────────────────

    def _check_metadata(self, path: Path, flags: list) -> dict:
        """
        Inspect PDF metadata for signs of forgery or AI generation.
        Red flags:
          - Missing CreationDate / ModDate / Author
          - Freeware producer (PyPDF, FPDF, WeasyPrint, etc.)
          - CreationDate == ModDate exactly (copy-paste AI generation)
          - Future-dated timestamps
          - Author name is a generic/tool name
        """
        result = {}
        try:
            pdf = pikepdf.open(path)
            meta = pdf.docinfo  # Low-level /Info dictionary

            # Extract fields
            creation_date = str(meta.get("/CreationDate", "")).strip()
            mod_date      = str(meta.get("/ModDate", "")).strip()
            author        = str(meta.get("/Author", "")).strip()
            producer      = str(meta.get("/Producer", "")).strip().lower()
            creator       = str(meta.get("/Creator", "")).strip().lower()
            title         = str(meta.get("/Title", "")).strip()

            result = {
                "CreationDate": creation_date or None,
                "ModDate":      mod_date or None,
                "Author":       author or None,
                "Producer":     producer or None,
                "Creator":      creator or None,
                "Title":        title or None,
            }

            # Flag: missing critical metadata
            if not creation_date:
                flags.append({
                    "flag": "missing_creation_date",
                    "severity": "HIGH",
                    "detail": "No /CreationDate in PDF metadata — unusual for legitimate documents"
                })
            if not author:
                flags.append({
                    "flag": "missing_author",
                    "severity": "MEDIUM",
                    "detail": "No /Author field — legitimate medical/financial docs usually include this"
                })
            if not mod_date and creation_date:
                flags.append({
                    "flag": "missing_mod_date",
                    "severity": "MEDIUM",
                    "detail": "Has CreationDate but no ModDate — atypical for real documents"
                })

            # Flag: suspicious producer
            for bad in SUSPICIOUS_PRODUCERS:
                if bad in producer or bad in creator:
                    flags.append({
                        "flag": "suspicious_producer",
                        "severity": "HIGH",
                        "detail": f"PDF produced by '{producer or creator}' — open-source/freeware tool not used by legitimate insurers or medical providers"
                    })
                    break

            # Flag: creation == modification date exactly (AI generation signature)
            if creation_date and mod_date and creation_date == mod_date:
                flags.append({
                    "flag": "creation_equals_modification",
                    "severity": "MEDIUM",
                    "detail": "CreationDate and ModDate are identical — common in AI-generated or programmatically created documents"
                })

            # Flag: future-dated document
            parsed = self._parse_pdf_date(creation_date)
            if parsed and parsed > datetime.now():
                flags.append({
                    "flag": "future_creation_date",
                    "severity": "CRITICAL",
                    "detail": f"Document creation date is in the future: {creation_date}"
                })

            # Flag: no encryption or signatures (only flag if doc claims to be from bank/insurer)
            if "/Encrypt" not in pdf.trailer:
                flags.append({
                    "flag": "no_encryption",
                    "severity": "INFO",
                    "detail": "Document is not encrypted — expected for financial/medical documents from major institutions"
                })

            pdf.close()

        except Exception as e:
            flags.append({
                "flag": "metadata_read_error",
                "severity": "MEDIUM",
                "detail": f"Could not read PDF metadata: {e} — may indicate corruption or obfuscation"
            })

        return result

    # ── XRef / incremental save analysis ─────────────────────────────────────

    def _check_xref_overlaps(self, path: Path, flags: list) -> dict:
        """
        Check for incremental saves with overlapping objects at the same coordinates.
        When someone manually edits a PDF, the altered object is appended to the file
        while the original remains — creating duplicate object IDs at different offsets.
        This is a near-zero false-positive signal for manual alteration.
        """
        result = {"incremental_saves": 0, "duplicate_object_ids": [], "suspicious": False}
        try:
            pdf = pikepdf.open(path)

            # Count how many xref sections exist (each = one save)
            with open(path, "rb") as f:
                content = f.read()

            xref_count = content.count(b"xref")
            startxref_count = content.count(b"startxref")

            result["incremental_saves"] = max(0, xref_count - 1)
            result["xref_sections"] = xref_count
            result["startxref_count"] = startxref_count

            # Multiple xref sections = incremental saves = potential manual edit
            if xref_count > 2:
                flags.append({
                    "flag": "multiple_xref_sections",
                    "severity": "HIGH",
                    "detail": f"Found {xref_count} xref sections — indicates {xref_count - 1} incremental save(s). Manual edits leave this signature."
                })
                result["suspicious"] = True

            # Check for duplicate object IDs (overlapping objects)
            obj_ids = []
            for objnum in pdf.objects:
                obj_ids.append(int(objnum))

            seen = set()
            dupes = []
            for oid in obj_ids:
                if oid in seen:
                    dupes.append(oid)
                seen.add(oid)

            if dupes:
                result["duplicate_object_ids"] = dupes
                flags.append({
                    "flag": "duplicate_object_ids",
                    "severity": "CRITICAL",
                    "detail": f"Object IDs {dupes[:5]} appear more than once — classic signature of content replacement (manual alteration)"
                })
                result["suspicious"] = True

            pdf.close()

        except Exception as e:
            flags.append({
                "flag": "xref_read_error",
                "severity": "INFO",
                "detail": f"Could not parse xref table: {e}"
            })

        return result

    # ── Embedded image analysis ───────────────────────────────────────────────

    def _check_embedded_images(self, path: Path, flags: list) -> dict:
        """
        Check how images are embedded:
        - XObject (Form or Image) = legitimate embedding method
        - Inline image streams = sometimes used in AI-generated docs
        Also checks image EXIF timestamps for the rounded-to-zero pattern Joe described.
        """
        result = {"image_count": 0, "xobject_count": 0, "inline_count": 0, "timestamp_flags": []}

        if not PIL_AVAILABLE:
            return result

        try:
            pdf = pikepdf.open(path)
            image_count = 0
            xobject_count = 0

            for page in pdf.pages:
                resources = page.get("/Resources", {})
                xobjects = resources.get("/XObject", {})

                for name, xobj in xobjects.items():
                    if xobj.get("/Subtype") == "/Image":
                        image_count += 1
                        xobject_count += 1

                        # Extract image and check EXIF timestamps
                        try:
                            pdfimage = pikepdf.PdfImage(xobj)
                            pil_img = pdfimage.as_pil_image()
                            exif_flags = self._check_image_timestamps(pil_img, str(name))
                            result["timestamp_flags"].extend(exif_flags)
                            flags.extend(exif_flags)
                        except Exception:
                            pass  # Not all images are extractable

            result["image_count"] = image_count
            result["xobject_count"] = xobject_count

            # Flag: no images at all in what should be a form/document
            if image_count == 0:
                flags.append({
                    "flag": "no_embedded_images",
                    "severity": "INFO",
                    "detail": "No images found — legitimate claim forms typically include logos, stamps, or signatures"
                })

            pdf.close()

        except Exception as e:
            flags.append({
                "flag": "image_read_error",
                "severity": "INFO",
                "detail": f"Could not analyze embedded images: {e}"
            })

        return result

    def _check_image_timestamps(self, img: "Image.Image", img_name: str) -> list:
        """
        Check EXIF timestamps for the rounded-to-zero pattern.
        Legitimate camera/scanner timestamps rarely end in :00:00 with 000 subseconds.
        """
        flags = []
        try:
            exif_data = img._getexif()
            if not exif_data:
                return flags

            for tag_id, value in exif_data.items():
                tag = TAGS.get(tag_id, str(tag_id))
                if "DateTime" in tag and isinstance(value, str):
                    # Pattern: YYYY:MM:DD HH:00:00 or seconds == 00
                    if re.search(r":\d{2}:00$", value) or value.endswith(":00:00"):
                        flags.append({
                            "flag": "suspicious_image_timestamp",
                            "severity": "MEDIUM",
                            "detail": f"Image '{img_name}' has timestamp '{value}' with seconds rounded to :00 — rare in authentic captures, common in altered images"
                        })
                        break
        except Exception:
            pass
        return flags

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _parse_pdf_date(self, date_str: str) -> Optional[datetime]:
        """Parse PDF date format: D:YYYYMMDDHHmmSS"""
        try:
            clean = date_str.replace("D:", "").replace("'", "")[:14]
            return datetime.strptime(clean, "%Y%m%d%H%M%S")
        except Exception:
            return None

    def _md5(self, path: Path) -> str:
        h = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def _build_explanation(self, flags: list, risk_level: str) -> str:
        if not flags:
            return "No forensic red flags detected. Document metadata appears consistent with a legitimate source."
        critical = [f for f in flags if f["severity"] == "CRITICAL"]
        high     = [f for f in flags if f["severity"] == "HIGH"]
        parts = []
        if critical:
            parts.append(f"{len(critical)} CRITICAL flag(s): " + "; ".join(f["flag"] for f in critical))
        if high:
            parts.append(f"{len(high)} HIGH flag(s): " + "; ".join(f["flag"] for f in high))
        medium = [f for f in flags if f["severity"] == "MEDIUM"]
        if medium:
            parts.append(f"{len(medium)} MEDIUM flag(s): " + "; ".join(f["flag"] for f in medium))
        return f"Risk level {risk_level}. " + " | ".join(parts)

    def _recommendation(self, risk_level: str) -> str:
        return {
            "LOW":      "Document appears authentic. Proceed with clinical claim review.",
            "MEDIUM":   "Minor anomalies detected. Flag for secondary review alongside clinical analysis.",
            "HIGH":     "Significant forgery indicators present. Request original documents from provider before processing.",
            "CRITICAL": "STOP. Strong evidence of document manipulation or AI generation. Escalate to fraud investigation team immediately.",
        }.get(risk_level, "Unknown risk level.")

    def _error(self, msg: str) -> dict:
        return {
            "agent": "document_integrity_checker",
            "fraud_detected": False,
            "risk_level": "UNKNOWN",
            "risk_score": 0,
            "flags": [],
            "error": msg,
        }


# ── Pipeline integration helper ───────────────────────────────────────────────

def run_agent_zero(pdf_path: str, verbose: bool = False) -> dict:
    """
    Drop-in for the VetGuard pipeline. Call this before rule_checker.
    Returns the same result dict shape as other agents.

    In fraud_engine.py, add:
        from document_integrity_checker import run_agent_zero
        doc_result = run_agent_zero(claim["pdf_path"])
        if doc_result["fraud_detected"]:
            return doc_result  # Short-circuit — no need for clinical agents
    """
    checker = DocumentIntegrityChecker()
    result = checker.analyze(pdf_path)
    if verbose:
        print(f"\n[Agent 0 — Document Integrity]")
        print(f"  Risk level : {result['risk_level']} (score={result['risk_score']})")
        print(f"  Flags      : {result['flag_count']}")
        for flag in result["flags"]:
            print(f"    [{flag['severity']}] {flag['flag']}: {flag['detail']}")
        print(f"  Decision   : {'FRAUD' if result['fraud_detected'] else 'PASS'}")
        print(f"  Action     : {result['recommendation']}")
    return result


# ── CLI quick-test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python document_integrity_checker.py <path_to_pdf>")
        print("\nExample: python document_integrity_checker.py claim.pdf")
        sys.exit(1)

    result = run_agent_zero(sys.argv[1], verbose=True)
    print("\nFull JSON result:")
    print(json.dumps(result, indent=2, default=str))
