const SECTOR_LABELS = {
  pharma: "Industrie pharmaceutique",
  biotech: "Biotechnologies",
  cosmetique: "Cosmétique",
  sante_diagnostic: "Santé et diagnostic",
  dispositifs_medicaux: "Dispositifs médicaux",
  agroalimentaire: "Agroalimentaire",
  environnement: "Environnement",
};

let ALL_OFFRES = [];
let LAST_RUN = null;
let activeSectors = new Set();
let activeDiploma = "";
let searchTerm = "";
let sortMode = "date-desc";

async function init() {
  try {
    const res = await fetch("data/offres.json?_=" + Date.now());
    const data = await res.json();
    ALL_OFFRES = data.offres || [];
    LAST_RUN = data.last_run;
  } catch (e) {
    console.error("Impossible de charger les offres", e);
    ALL_OFFRES = [];
  }

  buildSectorChips();
  buildDiplomaOptions();
  buildAboutList();
  renderStatusStrip();
  bindEvents();
  render();
}

function buildSectorChips() {
  const container = document.getElementById("sector-filters");
  const presentSectors = [...new Set(ALL_OFFRES.map(o => o.sector))];
  const sectorsToShow = presentSectors.length ? presentSectors : Object.keys(SECTOR_LABELS);

  sectorsToShow.forEach(sectorId => {
    const btn = document.createElement("button");
    btn.className = "chip";
    btn.textContent = SECTOR_LABELS[sectorId] || sectorId;
    btn.dataset.sector = sectorId;
    btn.addEventListener("click", () => {
      if (activeSectors.has(sectorId)) {
        activeSectors.delete(sectorId);
        btn.classList.remove("active");
      } else {
        activeSectors.add(sectorId);
        btn.classList.add("active");
      }
      render();
    });
    container.appendChild(btn);
  });
}

function buildDiplomaOptions() {
  const select = document.getElementById("diploma-filter");
  const levels = [...new Set(ALL_OFFRES.map(o => o.diploma_level).filter(Boolean))];
  levels.sort();
  levels.forEach(level => {
    const opt = document.createElement("option");
    opt.value = level;
    opt.textContent = level;
    select.appendChild(opt);
  });
}

function buildAboutList() {
  const ul = document.getElementById("about-sectors");
  Object.values(SECTOR_LABELS).forEach(label => {
    const li = document.createElement("li");
    li.textContent = label;
    ul.appendChild(li);
  });
}

function renderStatusStrip() {
  const el = document.getElementById("status-strip");
  if (!LAST_RUN) {
    el.textContent = "Données de démonstration — pas encore synchronisé";
    return;
  }
  const d = new Date(LAST_RUN);
  el.textContent = `${ALL_OFFRES.length} offres · dernière synchro ${d.toLocaleString("fr-FR")}`;
}

function bindEvents() {
  document.getElementById("search-input").addEventListener("input", (e) => {
    searchTerm = e.target.value.trim().toLowerCase();
    render();
  });
  document.getElementById("diploma-filter").addEventListener("change", (e) => {
    activeDiploma = e.target.value;
    render();
  });
  document.getElementById("sort-select").addEventListener("change", (e) => {
    sortMode = e.target.value;
    render();
  });
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById("tab-" + btn.dataset.tab).classList.add("active");
    });
  });
}

function render() {
  let list = ALL_OFFRES.filter(o => {
    if (activeSectors.size && !activeSectors.has(o.sector)) return false;
    if (activeDiploma && o.diploma_level !== activeDiploma) return false;
    if (searchTerm) {
      const haystack = `${o.title} ${o.company} ${o.city}`.toLowerCase();
      if (!haystack.includes(searchTerm)) return false;
    }
    return true;
  });

  list.sort((a, b) => {
    const da = typeof a.created_at === "string" ? a.created_at : "";
    const db = typeof b.created_at === "string" ? b.created_at : "";
    return sortMode === "date-desc" ? db.localeCompare(da) : da.localeCompare(db);
  });
  
  document.getElementById("results-meta").textContent =
    `${list.length} offre${list.length > 1 ? "s" : ""} affichée${list.length > 1 ? "s" : ""}`;

  const grid = document.getElementById("cards-grid");
  grid.innerHTML = "";
  document.getElementById("empty-state").hidden = list.length > 0;

  list.forEach(o => grid.appendChild(buildCard(o)));
}

function buildCard(o) {
  const card = document.createElement("article");
  card.className = "card";

  const sector = document.createElement("span");
  sector.className = "card-sector";
  sector.textContent = o.sector_label || SECTOR_LABELS[o.sector] || o.sector;
  card.appendChild(sector);

  const title = document.createElement("h3");
  title.className = "card-title";
  title.textContent = o.title;
  card.appendChild(title);

  const company = document.createElement("div");
  company.className = "card-company";
  company.textContent = o.company;
  card.appendChild(company);

  const meta = document.createElement("div");
  meta.className = "card-meta";
  const parts = [];
  if (o.city) parts.push(o.city);
  if (o.diploma_level) parts.push(o.diploma_level);
  if (o.contract_type) parts.push(o.contract_type);
  meta.textContent = parts.join(" · ");
  card.appendChild(meta);

  if (o.description) {
    const desc = document.createElement("p");
    desc.className = "card-desc";
    desc.textContent = o.description.length > 160 ? o.description.slice(0, 160) + "…" : o.description;
    card.appendChild(desc);
  }

  const link = document.createElement("a");
  link.className = "card-link";
  link.href = o.apply_url || "#";
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.textContent = "Voir l'offre";
  card.appendChild(link);

  return card;
}

init();
