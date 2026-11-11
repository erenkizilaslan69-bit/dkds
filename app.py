"""DKDS – Ders Kitabı Denetim Sistemi: Streamlit demo paneli.

Başlatma: DKDS_Baslat.bat (çift tıkla) ya da `streamlit run app.py`.
"""
from __future__ import annotations

import os
import tempfile
from collections import Counter
from pathlib import Path

import streamlit as st

from dkds import panel
from dkds.is_akisi import kitabi_analiz_et, sinifi_dosya_adindan_bul
from dkds.one_cikan import ONE_CIKANLAR, one_cikani_bul

KOK = Path(__file__).resolve().parent
# Klasörler ortam değişkeniyle değiştirilebilir (testler geçici klasör kullanır)
CIKTI = Path(os.environ.get("DKDS_CIKTI", KOK / "cikti"))
VERI = Path(os.environ.get("DKDS_VERI", KOK / "veri"))

st.set_page_config(page_title="DKDS – Ders Kitabı Denetim Sistemi", page_icon="📘", layout="wide")


# ------------------------------------------------------------------ yardımcılar


@st.cache_data(show_spinner=False)
def _kayit(yol: str, degisim: float) -> dict:
    """Hazır analiz kaydı (dosya değişince `degisim` değiştiği için önbellek yenilenir)."""
    return panel.kayit_yukle(Path(yol))


@st.cache_data(show_spinner=False, max_entries=64)
def _gorsel_yoldan(pdf_yolu: str, sayfa: int, paragraf, ara, olcek: float, yakin: bool) -> tuple[bytes, int]:
    """Her çağrıda belge yeniden açılır: işaret çizimi bellekteki kopyaya yapılır, önbellekteki belge kirlenmez."""
    belge = panel.acik_belge(pdf_yolu)
    try:
        isaret = panel.Isaret(sayfa, paragraf, ara)
        resim = panel.sayfayi_isaretle(belge, isaret, olcek, yakin)
        return resim, len(isaret.kelimeler)
    finally:
        belge.close()


def _gorsel(kaynak, isaret: panel.Isaret, yakin: bool, olcek: float = 1.5) -> tuple[bytes, int]:
    if isinstance(kaynak, (bytes, bytearray)):  # yüklenen PDF
        belge = panel.acik_belge(kaynak)
        try:
            resim = panel.sayfayi_isaretle(belge, isaret, olcek, yakin)
            return resim, len(isaret.kelimeler)
        finally:
            belge.close()
    return _gorsel_yoldan(str(kaynak), isaret.sayfa, isaret.paragraf, isaret.ara, olcek, yakin)


def _pdf_kaynagi(kayit: dict):
    """Sayfa görüntüsü için PDF: yüklenmişse baytları, hazır kitapsa veri/ klasöründeki yolu (yoksa None)."""
    yuklenen = st.session_state.get("yuklenen")
    if yuklenen and yuklenen["kayit"] is kayit:
        return yuklenen["bayt"]
    return panel.pdf_yolu(kayit, VERI)


def bulgu_detayi(kayit: dict, bulgu: dict, anahtar: str, ek=None, ara=None) -> None:
    """Bulgunun sayfasını kırmızı kutuyla gösterir; yanında açıklama ve öneri. Tutarlılıkta ilgili sayfalar yan yana."""
    kaynak = _pdf_kaynagi(kayit)
    isaretler = panel.bulgu_isaretleri(bulgu, ek, ara)
    cok_sayfa = len(isaretler) > 1

    st.markdown(f"**{panel.kriter_adi(bulgu['kriter'])} · {panel.tur_adi(bulgu['tur'])}** — "
                f"sayfa {bulgu['sayfa']}, paragraf {bulgu['paragraf']} · güven %{round(bulgu['guven'] * 100)}")
    if bulgu["tur"] in panel.CIKARIM_TURLERI:
        st.warning("Bu bulgu kitaptaki bir hatadan çok metin çıkarma sorunu olabilir; basılı sayfaya bakın.")
    yakin = st.toggle("Yalnızca işaretli bölgeyi göster (yakınlaştır)", value=cok_sayfa, key=f"yakin_{anahtar}")

    def metinler(yan_yana: bool = False) -> None:
        """Sorunlu metin, açıklama, öneri: yan yana (çok sayfalı) ya da alt alta."""
        kolonlar = st.columns(3) if yan_yana else [st.container()] * 3
        with kolonlar[0]:
            st.markdown("**Sorunlu metin**")
            st.info(bulgu["sorunlu_metin"])
        with kolonlar[1]:
            st.markdown("**Açıklama**")
            st.write(bulgu["aciklama"])
        with kolonlar[2]:
            if bulgu.get("oneri"):
                st.markdown("**Öneri**")
                st.success(bulgu["oneri"])
            st.progress(min(max(bulgu["guven"], 0.0), 1.0), text=f"Güven: {bulgu['guven']:.2f}")

    if kaynak is None:
        st.warning(f"Sayfa görüntüsü için PDF bulunamadı ({kayit.get('kaynak', '?')} veri/ klasöründe olmalı).")
        metinler()
        return

    if cok_sayfa:
        metinler(yan_yana=True)
        sutunlar = st.columns(len(isaretler))
        for sutun, isaret in zip(sutunlar, isaretler):
            with sutun:
                resim, bulunan = _gorsel(kaynak, isaret, yakin)
                st.image(resim, caption=isaret.baslik, width="stretch")
    else:
        sol, sag = st.columns([3, 2])
        with sol:
            resim, bulunan = _gorsel(kaynak, isaretler[0], yakin)
            st.image(resim, caption=isaretler[0].baslik, width="stretch")
        with sag:
            metinler()


def ozet_goster(kayit: dict) -> None:
    bulgular = kayit["bulgular"]
    sayac = Counter(b["kriter"] for b in bulgular)
    st.subheader("Kriter başına bulgu sayısı")
    sutunlar = st.columns(4)
    sutunlar[0].metric("Toplam bulgu", len(bulgular))
    for sutun, kriter in zip(sutunlar[1:], ("yazim", "okunabilirlik", "tutarlilik")):
        sutun.metric(panel.kriter_adi(kriter), sayac.get(kriter, 0))
    cikarim = sum(1 for b in bulgular if b["tur"] in panel.CIKARIM_TURLERI)
    if cikarim:
        st.caption(f"Bunların {cikarim} tanesi olası metin çıkarma sorunudur (bulgu tablosunda varsayılan olarak gizli).")

    tur_sayaci = Counter(panel.tur_adi(b["tur"]) for b in bulgular)
    if tur_sayaci:
        st.bar_chart(dict(tur_sayaci.most_common()), horizontal=True, height=40 + 32 * len(tur_sayaci))

    st.subheader("Okunabilirlik")
    oku = kayit.get("okunabilirlik_ozeti")
    if oku and not oku.get("atesman"):
        st.info("Ölçülecek yeterli gövde metni bulunamadığı için (birim sayısı "
                f"{oku.get('birim_sayisi', 0)}) kitabın okunabilirlik puanı hesaplanamadı.")
    elif oku:
        a, b = st.columns(2)
        a.metric("Ateşman okunabilirlik puanı", f"{oku['atesman']['puan']:.1f}", oku["atesman"]["duzey"],
                 delta_color="off", help="Yüksek puan = kolay metin. Türkçe ders kitaplarında ortalama 45-55 arasıdır.")
        b.metric("Bezirci-Yılmaz puanı", f"{oku['bezirci_yilmaz']['puan']:.1f}", oku["bezirci_yilmaz"]["duzey"],
                 delta_color="off", help="Yüksek puan = zor metin (okuyucunun sınıf düzeyine yakın bir ölçü).")
        ref = oku.get("referans", {})
        if ref.get("yontem") == "sinif_referansi":
            kaynak = "komşu sınıflardan ara değer" if ref.get("ara_deger") else ", ".join(ref.get("kitaplar", []))
            st.write(
                f"**Sınıf referansı ({ref['sinif']}. sınıf; {kaynak}):** referansın ortanca Ateşman puanı "
                f"{ref['ortanca']:.1f}, %10'luk zor dilim sınırı {ref['p10']:.1f}. Bu kitabın ortancası referanstan "
                f"{ref['medyan_farki']:+.1f} puan farklı (artı = referanstan kolay).")
        else:
            st.write(f"{ref.get('sinif')}. sınıf için referans tablosu yok; kitabın kendi %10'luk sınırı "
                     f"({ref.get('p10', 0):.1f}) kullanıldı.")
        st.write(f"**İşaretlenen birim:** {oku['isaretlenen_birim']} / {oku['birim_sayisi']} "
                 f"(%{oku['isaretlenen_oran'] * 100:.1f}; kitabın sınıfındaki kitaplarda beklenen ≈ %10).")
    else:
        st.info("Bu analizde sınıf düzeyi verilmediği için okunabilirlik hesaplanmadı.")

    st.subheader("Tutarlılık (kitap içi çelişkiler)")
    tut = kayit.get("tutarlilik_ozeti")
    if tut:
        a, b, c = st.columns(3)
        a.metric("Bulunan olgu (tarih + ölçü)", tut["olgu_sayisi"], f"{tut['varlikli_olgu']} tanesi bir varlıkla eşleşti",
                 delta_color="off")
        b.metric("Aday çelişki", tut["aday_celiski"])
        c.metric("Belirsiz çift", tut["belirsiz"], "LLM adımına gidecek" if tut["belirsiz"] else None, delta_color="off")
    uyarilar = kayit.get("uyarilar") or []
    if uyarilar:
        with st.expander(f"Çıkarım uyarıları ({len(uyarilar)})"):
            for u in uyarilar:
                st.write("• " + u)


def bulgular_sekmesi(kayit: dict, kitap_adi: str) -> None:
    bulgular = kayit["bulgular"]
    kriterler = sorted({b["kriter"] for b in bulgular})
    turler = sorted({b["tur"] for b in bulgular})
    f1, f2, f3, f4 = st.columns([2, 3, 2, 2])
    secili_kriter = f1.multiselect("Kriter", kriterler, default=kriterler, format_func=panel.kriter_adi, key="f_kriter")
    secili_tur = f2.multiselect("Bulgu türü", turler, default=[t for t in turler if t not in panel.CIKARIM_TURLERI],
                                format_func=panel.tur_adi, key="f_tur")
    en_dusuk = f3.slider("En düşük güven", 0.0, 1.0, 0.0, 0.05, key="f_guven")
    cikarim = f4.checkbox("Olası metin çıkarma sorunlarını göster", value=False, key="f_cikarim",
                          help="Çıkarım sorunu ve karakter kaybı türleri kitap hatası olmayabilir; varsayılan olarak gizli.")
    suzulen = panel.bulgulari_suz(bulgular, secili_kriter, secili_tur, en_dusuk, cikarim)
    satirlar = panel.tablo_satirlari(suzulen, kitap_adi)

    st.write(f"**{len(suzulen)}** bulgu gösteriliyor (toplam {len(bulgular)}).")
    ind1, ind2, _ = st.columns([1, 1, 4])
    ind1.download_button("CSV indir", panel.csv_bayt(satirlar), file_name=f"{kitap_adi}_bulgular.csv",
                         mime="text/csv", disabled=not satirlar, key="indir_csv")
    ind2.download_button("Excel indir", panel.excel_bayt(satirlar) if satirlar else b"",
                         file_name=f"{kitap_adi}_bulgular.xlsx", disabled=not satirlar, key="indir_excel",
                         mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    if not satirlar:
        st.info("Bu süzgeçle bulgu yok. Süzgeçleri gevşetin.")
        return

    gosterilen = [{k: v for k, v in s.items() if k != "Kitap"} for s in satirlar]
    secim = st.dataframe(gosterilen, on_select="rerun", selection_mode="single-row", hide_index=True,
                         width="stretch", height=320, key="bulgu_tablosu",
                         column_config={"Güven": st.column_config.NumberColumn(format="%.2f"),
                                        "Sorunlu metin": st.column_config.TextColumn(width="medium"),
                                        "Açıklama": st.column_config.TextColumn(width="large")})
    satir = secim.selection.rows
    st.divider()
    if not satir:
        st.info("Ayrıntıyı görmek için tablodan bir satır seçin: sayfa görüntüsünde bulgu kırmızı kutuyla işaretlenir.")
        return
    bulgu_detayi(kayit, suzulen[satir[0]], f"tablo_{satir[0]}_{kitap_adi}")


def one_cikanlar_sekmesi() -> None:
    st.write("Doğrulanmış örnekler: her biri basılı sayfayla karşılaştırıldı. Birine tıklayınca ilgili sayfa açılır.")
    hazir = panel.hazir_kayitlar(CIKTI)
    secili = st.session_state.get("one_cikan")
    for satir in (ONE_CIKANLAR[:3], ONE_CIKANLAR[3:]):
        for sutun, oge in zip(st.columns(3), satir):
            with sutun:
                if st.button(oge.baslik, key=f"oc_{oge.anahtar}", disabled=oge.kitap not in hazir, width="stretch",
                             type="primary" if oge.anahtar == secili else "secondary"):
                    st.session_state["one_cikan"] = secili = oge.anahtar
    if not secili:
        st.info("Yukarıdan bir örnek seçin.")
        return
    oge = next(o for o in ONE_CIKANLAR if o.anahtar == secili)
    st.divider()
    st.subheader(oge.baslik)
    st.write(oge.anlatim)
    kayit = _kayit(str(hazir[oge.kitap]), hazir[oge.kitap].stat().st_mtime)
    bulgu = one_cikani_bul(kayit["bulgular"], oge)
    if bulgu is None:
        st.error("Bu örnek şu anki analiz sonucunda bulunamadı (analiz kodu değişmiş olabilir).")
        return
    bulgu_detayi(kayit, bulgu, f"oc_{oge.anahtar}", ek=list(oge.ek), ara=oge.ara)


# ------------------------------------------------------------------ kenar çubuğu: kitap seçimi


def kitabi_sec() -> tuple[dict | None, str]:
    st.sidebar.title("📘 DKDS")
    st.sidebar.caption("Ders Kitabı Denetim Sistemi")
    kaynak = st.sidebar.radio("Kitap kaynağı", ["Hazır analiz", "Yeni PDF yükle"], key="kaynak_turu")
    if kaynak == "Hazır analiz":
        hazir = panel.hazir_kayitlar(CIKTI)
        if not hazir:
            st.sidebar.error("cikti/ klasöründe hazır analiz yok. Önce `python -m dkds on_hesapla` çalıştırın.")
            return None, ""
        adlar = list(hazir)
        etiketler = {ad: panel.kitap_etiketi(ad, _kayit(str(yol), yol.stat().st_mtime)) for ad, yol in hazir.items()}
        ad = st.sidebar.selectbox("Kitap", adlar, format_func=etiketler.get, key="hazir_kitap")
        return _kayit(str(hazir[ad]), hazir[ad].stat().st_mtime), ad

    dosya = st.sidebar.file_uploader("PDF dosyası", type="pdf", key="pdf_yukle")
    tahmin = sinifi_dosya_adindan_bul(dosya.name) if dosya else None
    sinif = st.sidebar.selectbox("Kitabın sınıf düzeyi", list(range(1, 13)), index=(tahmin or 5) - 1, key="sinif",
                                 help="Okunabilirlik, kitabı bu sınıfın referans dağılımıyla karşılaştırır.")
    if st.sidebar.button("Analiz et", type="primary", disabled=dosya is None, key="analiz_et"):
        bayt = dosya.getvalue()
        cubuk = st.sidebar.progress(0.0, text="Başlıyor…")
        with tempfile.TemporaryDirectory() as gecici:
            yol = Path(gecici) / dosya.name
            yol.write_bytes(bayt)
            kayit = kitabi_analiz_et(yol, sinif, ilerleme=lambda oran, ad: cubuk.progress(oran, text=ad))
        cubuk.empty()
        st.session_state["yuklenen"] = {"kayit": kayit, "bayt": bayt, "ad": Path(dosya.name).stem}
    yuklenen = st.session_state.get("yuklenen")
    if yuklenen:
        return yuklenen["kayit"], yuklenen["ad"]
    st.sidebar.info("PDF seçip sınıfı belirleyin, sonra «Analiz et»e basın. Büyük kitapta 20-60 saniye sürer.")
    return None, ""


def main() -> None:
    st.title("DKDS – Ders Kitabı Denetim Sistemi")
    st.caption("Yazım ve dil hataları · sınıf düzeyine uygunluk · kitap içi tutarlılık")
    kayit, kitap_adi = kitabi_sec()
    sekme_ozet, sekme_bulgu, sekme_one = st.tabs(["📊 Özet", "🔎 Bulgular", "⭐ Öne çıkan bulgular"])
    with sekme_one:
        one_cikanlar_sekmesi()
    if kayit is None:
        with sekme_ozet:
            st.info("Soldan bir kitap seçin ya da yeni bir PDF yükleyin.")
        return
    with sekme_ozet:
        st.header(f"{kayit.get('kaynak', kitap_adi)} – {kayit.get('sayfa_sayisi', '?')} sayfa")
        ozet_goster(kayit)
    with sekme_bulgu:
        bulgular_sekmesi(kayit, kitap_adi)


main()
