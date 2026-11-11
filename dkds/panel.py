"""Demo panelinin (app.py) Streamlit'ten bağımsız işlevleri: kayıt okuma, süzme, sayfa görüntüsü, dışa aktarma.

Ayrı tutulmasının nedeni: bu mantık arayüz olmadan test edilebilir (tests/test_panel.py) ve
app.py yalnızca ekranı kurar.
"""
from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from pathlib import Path

try:
    import pymupdf as fitz
except ImportError:  # eski PyMuPDF sürümleri
    import fitz

CIKTI_KLASORU = Path("cikti")
VERI_KLASORU = Path("veri")

KRITER_ADLARI = {"yazim": "Yazım", "okunabilirlik": "Okunabilirlik", "tutarlilik": "Tutarlılık"}
TUR_ADLARI = {
    "tekrar": "Kelime tekrarı", "bilinmeyen_kelime": "Bilinmeyen kelime", "karakter_kaybi": "Karakter kaybı (çıkarım)",
    "cikarim_sorunu": "Olası metin çıkarma sorunu", "tarih_celiskisi": "Tarih çelişkisi",
    "sayisal_celiski": "Sayısal çelişki", "sinif_ustu": "Sınıf düzeyinin üstünde",
    "noktalama_oncesi_bosluk": "Noktalama öncesi boşluk", "noktalama_sonrasi_bosluk": "Noktalama sonrası boşluk",
    "kucuk_harfle_cumle": "Cümle küçük harfle başlıyor", "sik_yanlis": "Sık yapılan yazım yanlışı",
    "bosluklu_tire": "Boşluklu tire",
}
# Metin çıkarma hatasından kaynaklanması olası bulgu türleri: varsayılan olarak gizlenir
CIKARIM_TURLERI = ("cikarim_sorunu", "karakter_kaybi")
SUTUNLAR = ("Kitap", "Sayfa", "Paragraf", "Kriter", "Tür", "Sorunlu metin", "Açıklama", "Öneri", "Güven", "İlgili sayfa")


def kriter_adi(kriter: str) -> str:
    return KRITER_ADLARI.get(kriter, kriter)


def tur_adi(tur: str) -> str:
    return TUR_ADLARI.get(tur, tur or "—")


# ------------------------------------------------------------------ kayıtlar


def hazir_kayitlar(klasor: Path = CIKTI_KLASORU) -> dict[str, Path]:
    """cikti/ klasöründeki hazır analiz sonuçları: {kitap adı: yol}. Yalnızca `on_hesapla`/`analiz` çıktıları
    (içinde "bulgular" ve "sinif" olanlar) alınır; ham çıkarım dosyaları (kitap.json) atlanır."""
    kayitlar: dict[str, Path] = {}
    for yol in sorted(Path(klasor).glob("*_bulgular.json")):
        try:
            kayit = json.loads(yol.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(kayit, dict) and "bulgular" in kayit and "sinif" in kayit:
            kayitlar[yol.name[: -len("_bulgular.json")]] = yol
    return kayitlar


def kayit_yukle(yol: Path) -> dict:
    return json.loads(Path(yol).read_text(encoding="utf-8"))


def kitap_etiketi(ad: str, kayit: dict | None = None) -> str:
    sinif = (kayit or {}).get("sinif")
    return f"{ad} ({sinif}. sınıf)" if sinif else ad


def pdf_yolu(kayit: dict, klasor: Path = VERI_KLASORU) -> Path | None:
    """Kaydın PDF'i veri/ klasöründeyse yolu, yoksa None."""
    yol = Path(klasor) / kayit.get("kaynak", "")
    return yol if kayit.get("kaynak") and yol.exists() else None


# ------------------------------------------------------------------ süzme ve tablo


def bulgulari_suz(bulgular: list[dict], kriterler=None, turler=None, en_dusuk_guven: float = 0.0,
                  cikarim_sorunlarini_goster: bool = False) -> list[dict]:
    """Kriter, tür ve en düşük güvene göre süzer; çıkarım şüphesi türleri varsayılan olarak gizlidir.
    `kriterler`/`turler` None ise hepsi."""
    sonuc = []
    for b in bulgular:
        if kriterler is not None and b["kriter"] not in kriterler:
            continue
        if turler is not None and b["tur"] not in turler:
            continue
        if b["guven"] < en_dusuk_guven:
            continue
        if not cikarim_sorunlarini_goster and b["tur"] in CIKARIM_TURLERI:
            continue
        sonuc.append(b)
    return sonuc


def tablo_satirlari(bulgular: list[dict], kitap: str = "") -> list[dict]:
    """Ekranda ve dışa aktarmada kullanılan Türkçe sütunlu satırlar."""
    return [
        {
            "Kitap": kitap, "Sayfa": b["sayfa"], "Paragraf": b["paragraf"], "Kriter": kriter_adi(b["kriter"]),
            "Tür": tur_adi(b["tur"]), "Sorunlu metin": b["sorunlu_metin"], "Açıklama": b["aciklama"],
            "Öneri": b.get("oneri") or "", "Güven": round(b["guven"], 2), "İlgili sayfa": b.get("ilgili_sayfa") or "",
        }
        for b in bulgular
    ]


def csv_bayt(satirlar: list[dict]) -> bytes:
    """Excel'in Türkçe karakterleri doğru açması için BOM'lu UTF-8, noktalı virgül ayraçlı CSV."""
    cikti = io.StringIO()
    yazici = csv.DictWriter(cikti, fieldnames=SUTUNLAR, delimiter=";", lineterminator="\r\n")
    yazici.writeheader()
    yazici.writerows(satirlar)
    return cikti.getvalue().encode("utf-8-sig")


def excel_bayt(satirlar: list[dict]) -> bytes:
    import pandas as pd

    cikti = io.BytesIO()
    with pd.ExcelWriter(cikti, engine="openpyxl") as yazar:
        pd.DataFrame(satirlar, columns=list(SUTUNLAR)).to_excel(yazar, sheet_name="Bulgular", index=False)
        sayfa = yazar.sheets["Bulgular"]
        for sutun, genislik in zip("ABCDEFGHIJ", (14, 8, 9, 14, 24, 60, 70, 50, 8, 12)):
            sayfa.column_dimensions[sutun].width = genislik
    return cikti.getvalue()


# ------------------------------------------------------------------ sayfa görüntüsü


@dataclass
class Isaret:
    """Sayfa görüntüsünde işaretlenecek yer: `paragraf` kutusu ve (bulunursa) içindeki `ara` ifadesinin kutuları."""

    sayfa: int
    paragraf: tuple[float, float, float, float] | None = None
    ara: str | None = None  # paragraf içinde ayrıca kalın çerçevelenecek ifade
    baslik: str = ""
    kelimeler: list = field(default_factory=list)  # sayfayi_isaretle doldurur: [(x0, y0, x1, y1)]


def _bosluklari_birlestir(metin: str) -> str:
    return " ".join(metin.split())


def kelime_kutulari(sayfa, paragraf_kutusu, ara: str | None) -> list[tuple[float, float, float, float]]:
    """`ara` ifadesinin sayfadaki konumları (PyMuPDF araması). Paragraf kutusu verilmişse yalnızca onun içinde
    aranır; bulunamazsa boş liste."""
    if not ara:
        return []
    alan = (fitz.Rect(paragraf_kutusu) + (-3, -3, 3, 3)) if paragraf_kutusu else None
    for aday in (_bosluklari_birlestir(ara), ara.replace(" ", " "), ara.rstrip(" .")):
        bulunan = sayfa.search_for(aday, clip=alan) if alan else sayfa.search_for(aday)
        if bulunan:
            return [tuple(r) for r in bulunan]
    return []


def sayfayi_isaretle(belge, isaret: Isaret, olcek: float = 1.5, yakinlastir: bool = False) -> bytes:
    """Sayfayı PNG baytlarına çevirir; paragraf konumu kırmızı kutuyla, `ara` bulunduysa o ifade kalın kırmızı
    kutu ve açık renk vurguyla işaretlenir. `yakinlastir` doğruysa yalnızca işaretli bölge (üst-alt 90 pt payla)
    gösterilir. İşaretler geçici açıklama (annotation) olarak eklenir ve çizimden sonra silinir: belge ve PDF
    dosyası değişmez, aynı belgeyle art arda çağrılabilir."""
    sayfa = belge[isaret.sayfa - 1]
    isaret.kelimeler = kelime_kutulari(sayfa, isaret.paragraf, isaret.ara)
    kirmizi = (0.85, 0.05, 0.05)
    eklenen = []
    try:
        if isaret.paragraf:
            kutu = sayfa.add_rect_annot(fitz.Rect(isaret.paragraf) + (-2, -2, 2, 2))
            kutu.set_colors(stroke=kirmizi)
            kutu.set_border(width=1.2)
            kutu.update()
            eklenen.append(kutu)
        for k in isaret.kelimeler:
            vurgu = sayfa.add_highlight_annot(fitz.Rect(k))
            vurgu.set_colors(stroke=(1.0, 0.85, 0.5))
            vurgu.update()
            kutu = sayfa.add_rect_annot(fitz.Rect(k) + (-1.5, -1, 1.5, 1))
            kutu.set_colors(stroke=kirmizi)
            kutu.set_border(width=2.4)
            kutu.update()
            eklenen += [vurgu, kutu]
        kesit = None
        odak = isaret.paragraf or (isaret.kelimeler[0] if isaret.kelimeler else None)
        if yakinlastir and odak:
            r = fitz.Rect(odak)
            kesit = fitz.Rect(sayfa.rect.x0, max(sayfa.rect.y0, r.y0 - 90), sayfa.rect.x1,
                              min(sayfa.rect.y1, r.y1 + 90))
        return sayfa.get_pixmap(matrix=fitz.Matrix(olcek, olcek), clip=kesit, annots=True).tobytes("png")
    finally:
        for ek in eklenen:
            sayfa.delete_annot(ek)


def acik_belge(kaynak):
    """Yol (str/Path) ya da PDF baytlarıyla PyMuPDF belgesi açar."""
    if isinstance(kaynak, (bytes, bytearray)):
        return fitz.open(stream=bytes(kaynak), filetype="pdf")
    return fitz.open(str(kaynak))


def bulgu_isaretleri(bulgu: dict, ek: list[tuple[int, str]] | None = None,
                     ara: dict[int, str] | None = None) -> list[Isaret]:
    """Bulgunun gösterilecek sayfaları ve kutuları: asıl yer, tutarlılıkta ilgili yer, varsa ek sayfalar.

    `ara`: {sayfa: ifade} ile o sayfada ifade kutusu istenir; verilmezse yazım bulgusunda `sorunlu_metin`
    (kısaysa) aranır. `ek`: paragraf konumu bulguda olmayan, ifadesiyle bulunacak ek sayfalar."""
    ara = ara or {}
    asil_ara = ara.get(bulgu["sayfa"])
    if asil_ara is None and bulgu["kriter"] == "yazim" and len(bulgu["sorunlu_metin"]) <= 40:
        asil_ara = bulgu["sorunlu_metin"]
    isaretler = [Isaret(bulgu["sayfa"], _kutu(bulgu.get("konum")), asil_ara, f"Sayfa {bulgu['sayfa']}")]
    if bulgu.get("ilgili_sayfa"):
        isaretler.append(Isaret(bulgu["ilgili_sayfa"], _kutu(bulgu.get("ilgili_konum")), ara.get(bulgu["ilgili_sayfa"]),
                                f"Sayfa {bulgu['ilgili_sayfa']} (çelişen yer)"))
    for sayfa, ifade in ek or []:
        isaretler.append(Isaret(sayfa, None, ifade, f"Sayfa {sayfa} (destekleyen yer)"))
    return isaretler


def _kutu(konum) -> tuple[float, float, float, float] | None:
    return tuple(konum) if konum else None
