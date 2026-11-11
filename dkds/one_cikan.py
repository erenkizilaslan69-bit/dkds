"""Sunumda kullanılan, basılı sayfayla doğrulanmış öne çıkan bulgular (bkz. CLAUDE.md)."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class OneCikan:
    anahtar: str
    kitap: str  # cikti/<kitap>_bulgular.json
    baslik: str
    anlatim: str  # sunumda söylenecek tek cümle
    kriter: str
    sayfa: int
    metin: str | None = None  # sorunlu_metin içinde geçmesi gereken parça
    ilgili_sayfa: int | None = None
    ek: tuple[tuple[int, str], ...] = ()  # (sayfa, ifade): bulguda konumu olmayan destekleyen yerler
    ara: dict = field(default_factory=dict)  # {sayfa: ifade}: kutu içinde ayrıca çerçevelenecek ifade
    beklenen: dict = field(default_factory=dict)  # {sayfa: basılı sayfada kutunun içinde olması gereken metin}


ONE_CIKANLAR: tuple[OneCikan, ...] = (
    OneCikan("fen5_s31", "fen5", "fen5 s.31 – yarım kalmış kelime",
             "Cümle «hedeflenmektedi .» diye bitiyor; «hedeflenmektedir.» olmalı.",
             "yazim", 31, "hedeflenmektedi", beklenen={31: "hedeflenmektedi"}),
    OneCikan("fen5_s124", "fen5", "fen5 s.124 – yarım kalmış kelime",
             "«sınıflandırılı .» yazılmış; «sınıflandırılır.» olmalı.",
             "yazim", 124, "sınıflandırılı", beklenen={124: "sınıflandırılı"}),
    OneCikan("sosyal5_s79", "sosyalbilgiler5", "sosyalbilgiler5 s.79 – harf eksik",
             "«öğretmlerimiz» yazılmış; «öğretmenlerimiz» olmalı.",
             "yazim", 79, "öğretmlerimiz", beklenen={79: "öğretmlerimiz"}),
    OneCikan("sosyal5_s37", "sosyalbilgiler5", "sosyalbilgiler5 s.37 – yanlış yazım",
             "«anektod» yazılmış; doğrusu «anekdot».",
             "yazim", 37, "anektod", beklenen={37: "anektod"}),
    OneCikan("turkce5_s35", "turkce5", "turkce5 s.35 – çok uzun cümle",
             "Paragraf 5. sınıf kitaplarının %10'luk zor dilimine giriyor; kitabın kendi «uzun cümleyi böl» etkinliği.",
             "okunabilirlik", 35, beklenen={35: ""}),
    OneCikan("sosyal5_catalhoyuk", "sosyalbilgiler5", "sosyalbilgiler5 – Çatalhöyük tarihi",
             "s.112 «MÖ 7500» (= 9.500 yıl önce) ve s.147 «9 500 yıl önce» tutarlı; s.118 «yaklaşık 9000 yıl önce» "
             "diyor: 500 yıl fark.",
             "tutarlilik", 118, ilgili_sayfa=112, ek=((147, "9 500 yıl önce"),),
             ara={118: "yaklaşık 9000 yıl önce", 112: "MÖ 7500"},
             beklenen={118: "9000 yıl önce", 112: "MÖ 7500", 147: "9 500 yıl önce"}),
)


def one_cikani_bul(bulgular: list[dict], oge: OneCikan) -> dict | None:
    """Kayıttaki bulgular arasında bu öne çıkan örneğe karşılık geleni bulur; yoksa None."""
    for b in bulgular:
        if b["kriter"] != oge.kriter or b["sayfa"] != oge.sayfa:
            continue
        if oge.metin and oge.metin not in b["sorunlu_metin"]:
            continue
        if oge.ilgili_sayfa and b.get("ilgili_sayfa") != oge.ilgili_sayfa:
            continue
        return b
    return None
