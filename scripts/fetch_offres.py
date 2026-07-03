#!/usr/bin/env python3
"""
Recherche Alternance - fetch_offres.py

Interroge l'API publique "La Bonne Alternance" (api.apprentissage.beta.gouv.fr)
pour chaque secteur défini dans sectors.yaml, dédoublonne les résultats et
maintient une archive JSON consommée par le site statique.

Variables d'environnement attendues :
  LBA_API_TOKEN   Jeton d'accès personnel (Bearer token)
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
SECTORS_FILE = ROOT / "sectors.yaml"
ARCHIVE_FILE = ROOT / "docs" / "data" / "offres.json"
MAX_ARCHIVE_SIZE = 1500

API_BASE = "https://api.apprentissage.beta.gouv.fr/api/job/v1/search"
REQUEST_TIMEOUT = 20
PAUSE_BETWEEN_CALLS = 1.1  # reste large sous la limite de 60 appels/minute


def load_sectors():
    with open(SECTORS_FILE, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config["sectors"]


def load_archive():
    if ARCHIVE_FILE.exists():
        with open(ARCHIVE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"last_run": None, "offres": []}


def save_archive(archive):
    ARCHIVE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(ARCHIVE_FILE, "w", encoding="utf-8") as f:
        json.dump(archive, f, ensure_ascii=False, indent=2)


def fetch_sector_offers(sector, token):
    """Appelle l'API pour un secteur (regroupe ses codes ROME en un seul appel)."""
    romes = ",".join(sector["romes"])
    params = {"romes": romes}

    headers = {"Authorization": f"Bearer {token}"}

    try:
        resp = requests.get(API_BASE, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        print(f"  [ERREUR] {sector['id']}: échec de connexion ({exc})", file=sys.stderr)
        return []

    if resp.status_code != 200:
        print(f"  [ERREUR] {sector['id']}: HTTP {resp.status_code} - {resp.text[:300]}", file=sys.stderr)
        return []

    data = resp.json()
    jobs = data.get("jobs", []) or []

    if os.environ.get("DEBUG_LBA"):
        print(f"  [DEBUG] clés racine de la réponse: {list(data.keys())}", file=sys.stderr)
        print(f"  [DEBUG] nb jobs bruts: {len(jobs)}", file=sys.stderr)
        if jobs:
            j0 = jobs[0]
            print(f"  [DEBUG] identifier: {json.dumps(j0.get('identifier'), ensure_ascii=False)}", file=sys.stderr)
            print(f"  [DEBUG] offer: {json.dumps(j0.get('offer'), ensure_ascii=False)}", file=sys.stderr)
            print(f"  [DEBUG] contract: {json.dumps(j0.get('contract'), ensure_ascii=False)}", file=sys.stderr)
            print(f"  [DEBUG] apply: {json.dumps(j0.get('apply'), ensure_ascii=False)}", file=sys.stderr)
        if data.get("warnings"):
            print(f"  [DEBUG] warnings API: {data['warnings']}", file=sys.stderr)

    results = []
    for job in jobs:
        try:
            offer_id = job.get("id") or job.get("_id")
            title = (job.get("title") or "").strip()
            if not offer_id or not title:
                continue

            company = (job.get("workplace", {}) or {}).get("name") or (job.get("company", {}) or {}).get("name") or "Entreprise non précisée"
            location = (job.get("workplace", {}) or {}).get("address", {}) or {}
            city = location.get("city") or ""
            department = location.get("department") or {}
            dept_label = department.get("name") if isinstance(department, dict) else department

            apply_url = (job.get("apply", {}) or {}).get("url") or job.get("url") or ""

            results.append({
                "id": offer_id,
                "sector": sector["id"],
                "sector_label": sector["label"],
                "title": title,
                "company": company,
                "city": city,
                "department": dept_label,
                "diploma_level": (job.get("target_diploma", {}) or {}).get("label"),
                "contract_type": job.get("contract", {}).get("type") if isinstance(job.get("contract"), dict) else None,
                "created_at": job.get("created_at") or job.get("createdAt"),
                "apply_url": apply_url,
                "description": (job.get("description") or "")[:600],
            })
        except Exception as exc:  # tolère les champs inattendus/API en évolution
            print(f"  [WARN] offre ignorée ({exc})", file=sys.stderr)
            continue

    return results


def main():
    token = os.environ.get("LBA_API_TOKEN")
    if not token:
        print("[ERREUR] Variable d'environnement LBA_API_TOKEN manquante.", file=sys.stderr)
        sys.exit(1)

    sectors = load_sectors()
    archive = load_archive()
    existing_ids = {o["id"] for o in archive["offres"]}

    new_count = 0
    all_fresh = []

    for sector in sectors:
        print(f"-> Secteur: {sector['label']} ({', '.join(sector['romes'])})")
        offers = fetch_sector_offers(sector, token)
        print(f"   {len(offers)} offre(s) reçue(s)")
        all_fresh.extend(offers)
        time.sleep(PAUSE_BETWEEN_CALLS)

    # Dédoublonnage : une offre peut remonter sous plusieurs secteurs si ses
    # codes ROME se recoupent. On garde la première occurrence rencontrée.
    seen_this_run = {}
    for offer in all_fresh:
        if offer["id"] not in seen_this_run:
            seen_this_run[offer["id"]] = offer

    for offer_id, offer in seen_this_run.items():
        if offer_id not in existing_ids:
            archive["offres"].append(offer)
            existing_ids.add(offer_id)
            new_count += 1

    # Trie par date de création décroissante quand disponible, puis tronque
    def sort_key(o):
        return o.get("created_at") or ""

    archive["offres"].sort(key=sort_key, reverse=True)
    archive["offres"] = archive["offres"][:MAX_ARCHIVE_SIZE]
    archive["last_run"] = datetime.now(timezone.utc).isoformat()

    save_archive(archive)
    print(f"\nTerminé. {new_count} nouvelle(s) offre(s) ajoutée(s). Total archive: {len(archive['offres'])}")


if __name__ == "__main__":
    main()
