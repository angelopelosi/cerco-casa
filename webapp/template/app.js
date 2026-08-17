async function main() {
  try {
    const response = await fetch("data.json");
    const listings = await response.json();
    populateFonteOptions(listings);
    render(listings);
    document.getElementById("filters").addEventListener("input", () => render(listings));
  } catch (error) {
    const container = document.getElementById("listings");
    container.textContent = "Errore nel caricamento degli annunci";
  }
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
  const chiVende = document.getElementById("f-chi-vende").value;

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
    if (chiVende && l.chi_vende !== chiVende) return false;
    return true;
  });
}

function render(allListings) {
  const filtered = applyFilters(allListings);
  const container = document.getElementById("listings");
  container.innerHTML = "";

  if (filtered.length === 0) {
    const p = document.createElement("p");
    p.textContent = "Nessun annuncio corrisponde ai filtri.";
    container.appendChild(p);
    return;
  }

  for (const l of filtered) {
    const card = document.createElement("div");
    card.className = "card";

    const h3 = document.createElement("h3");
    const a = document.createElement("a");
    a.target = "_blank";
    a.rel = "noopener";
    a.textContent = l.titolo;
    if (l.url && (l.url.startsWith("http://") || l.url.startsWith("https://"))) {
      a.href = l.url;
    } else {
      a.href = "#";
    }
    h3.appendChild(a);
    card.appendChild(h3);

    const p1 = document.createElement("p");
    const tipoText = l.tipo || "";
    const prezzoText = l.prezzo ? l.prezzo + "€" : "";
    const comuneText = l.comune || "";
    const fonteText = l.fonte || "";
    const parts = [tipoText, prezzoText, comuneText, fonteText].filter(s => s);
    p1.textContent = parts.join(" — ");
    card.appendChild(p1);

    const p2 = document.createElement("p");
    const mqText = l.superficie_mq ? l.superficie_mq + " mq" : "";
    const arredatoText = l.arredato && l.arredato !== "non_specificato" ? "· arredato: " + l.arredato : "";
    const chiVendeText = l.chi_vende ? "· " + l.chi_vende : "";
    const detailParts = [mqText, arredatoText, chiVendeText].filter(s => s);
    p2.textContent = detailParts.join(" ");
    card.appendChild(p2);

    container.appendChild(card);
  }
}

main();
