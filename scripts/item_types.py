"""Item types, so the site can filter posts by what's in them (a watch on an outfit post still shows under Wrist)."""
import re

TYPES = ("watch", "sneakers", "shoes", "clothing", "bag", "jewelry", "accessory")

_WATCH = r"\bwatch|rolex|omega|cartier|audemars|royal oak|code 11\.59|tudor|breitling|patek|richard mille|\brm ?\d|hublot|seiko|tissot|casio|peugeot|\bday[- ]date|fluted bezel|roman numeral|g-?shock|citizen|orient|piaget|fossil|timex|daytona|speedmaster|seamaster|aqua terra|navitimer|santos|\btank\b|tonneau|tortue|day-date|oyster perpetual|black bay|tambour|chronograph|diver\b|guichets|navihawk|kamasu|presage|speedtimer|\bprx\b"
_SNEAK = r"sneaker|trainer|\bnike\b|jordan|adidas|samba|gazelle|new balance|\b9060\b|asics|kayano|converse|chuck|\bshai 001|\bpuma\b|speedcat|moon shoe|air max|air force|\baf1\b|\bvans\b|skate shoe|skate sneaker|running shoe|collapse sneaker|goadome|zoom vapor|\b11s?\b.*jordan"
_SHOES = r"loafer|boot|oxford shoe|derby|brogue|wingtip|mule|sandal|slide|dress shoe|monk strap"
_BAG = r"\bbag\b|handbag|tote|backpack|crossbody|purse|clutch|duffel"
_JEWEL = r"chain|necklace|pendant|ring\b|bracelet(?!.*watch)|earring|grill"
_CLOTH = r"\bshorts?\b|\bvest\b|shirt|jacket|hoodie|sweat|pants|trousers|jeans|\btee\b|t-shirt|jersey|tracksuit|\bset\b|suit\b|blazer|coat|sweater|cardigan|polo"
_ACC = r"\bbelt\b|\btie\b|sunglasses|glasses|\bhat\b|\bcap\b|beanie|scarf|gloves|socks|wallet"


def guess_type(text, brand=""):
    t = f"{brand} {text}".lower()
    # order matters: "watch" beats brand words, shoes before sneakers for loafers/boots from sneaker brands
    if re.search(_WATCH, t) and not re.search(r"\bwatch(ing)?\b.*(cap|hat)", t):
        if not re.search(_SHOES + "|" + _BAG, t) or re.search(r"\bwatch\b", t):
            return "watch"
    if re.search(_SHOES, t) and not re.search(r"sneaker boot", t):
        return "shoes"
    if re.search(_SNEAK + r"|sneaker boot", t) and not (re.search(_CLOTH, t) and not re.search(r"sneaker|shoe|trainer|\b9060\b|samba|jordan 1|air force|moon shoe|air max|vapor|kayano|shai 001", t)):
        return "sneakers"
    if re.search(_BAG, t):
        return "bag"
    if re.search(_JEWEL, t):
        return "jewelry"
    if re.search(_ACC, t):
        return "accessory"
    return "clothing"
