async function main() {
  const response = await fetch("data.json");
  const listings = await response.json();
  populateFonteOptions(listings);
  render(listings);
  document.getElementById("filters").addEventListener("input", () => render(listings));
}

function populateFonteOptions(listings) {
  const select = document.getElementById("f-fonte");
  const fonti = [...new Set(listings.map((l) => l.fonte))].sort();
  for (const fonte of fonti) {
    const opt = document.createElement("option");
    opt.value = fonte;
    opt.textContent = fonte;
    select.appendChild(opt);
  }
}

function applyFilters(listings) {
  const tipo = document.getElementById("f-tipo").value;
  const prezzoMin = parseFloat(document.getElementById("f-prezzo-min").value) || null;
  const prezzoMax = parseFloat(document.getElementById("f-prezzo-max").value) || null;
  const mqMin = parseFloat(document.getElementById("f-mq-min").value) || null;
  const mqMax = parseFloat(document.getElementById("f-mq-max").value) || null;
  const comune = document.getElementById("f-comune").value.trim().toLowerCase();
  const fonte = document.getElementById("f-fonte").value;
  const disponibilita = document.getElementById("f-disponibilita").value;
  const arredato = document.getElementById("f-arredato").value;

  return listings.filter((l) => {
    if (tipo && l.tipo !== tipo) return false;
    if (prezzoMin !== null && l.prezzo < prezzoMin) return false;
    if (prezzoMax !== null && l.prezzo > prezzoMax) return false;
    if (mqMin !== null && (l.superficie_mq === null || l.superficie_mq < mqMin)) return false;
    if (mqMax !== null && (l.superficie_mq === null || l.superficie_mq > mqMax)) return false;
    if (comune && !(l.comune || "").toLowerCase().includes(comune)) return false;
    if (fonte && l.fonte !== fonte) return false;
    if (disponibilita && l.stato_disponibilita !== disponibilita) return false;
    if (arredato && l.arredato !== arredato) return false;
    return true;
  });
}

function render(allListings) {
  const filtered = applyFilters(allListings);
  const container = document.getElementById("listings");
  container.innerHTML = filtered
    .map(
      (l) => `
      <div class="card">
        <h3><a href="${l.url}" target="_blank" rel="noopener">${l.titolo}</a></h3>
        <p>${l.tipo} — ${l.prezzo}€ — ${l.comune || ""} — ${l.fonte}</p>
        <p>${l.superficie_mq ? l.superficie_mq + " mq" : ""} ${l.arredato !== "non_specificato" ? "· arredato: " + l.arredato : ""}</p>
      </div>`
    )
    .join("");
  if (filtered.length === 0) {
    container.innerHTML = "<p>Nessun annuncio corrisponde ai filtri.</p>";
  }
}

main();
