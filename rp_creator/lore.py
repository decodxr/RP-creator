import re
import unicodedata


# Canon reference for Demon Slayer / Kimetsu no Yaiba.
# This is intentionally an original, compact reference guide rather than a copy
# of manga/anime text. It is writer knowledge: NPCs must not automatically know it.
DEMON_SLAYER_LORE = [
    {
        "id": "core-setting",
        "core": True,
        "tags": "demon slayer kimetsu taisho japao mundo noite demonios cacadores sociedade",
        "text": """SETTING — Demon Slayer takes place mainly in Taisho-era Japan. Most ordinary people do not know that demons exist. Demons hide among humans, usually act at night and feed on human flesh. The Demon Slayer Corps is an old, unofficial organization dedicated to hunting them. It operates outside normal government recognition, using hidden estates, swordsmiths, medics, Kakushi support staff and Kasugai crows to keep missions moving. Technology and customs are mixed: rural villages and traditional clothing coexist with trains, electric lights and growing cities."""
    },
    {
        "id": "core-demons",
        "core": True,
        "tags": "demon demonio oni muzan sangue regeneracao sol nichirin glicinia wisteria arte demoníaca",
        "text": """DEMON RULES — Nearly all demons originate from Muzan Kibutsuji's blood. They possess superhuman strength, speed, senses and regeneration, and stronger demons can develop unique Blood Demon Arts. Their principal natural weakness is sunlight. A Demon Slayer normally kills a demon by decapitating it with a Nichirin weapon; wisteria-derived poison can also be lethal or debilitating. A demon's regeneration, hunger, tolerance and abilities vary enormously. Consuming more humans generally increases power. Muzan can manipulate or destroy many demons through his blood, and demons commonly fear him. Nezuko is a major exception to normal demon behavior because she resists eating humans and eventually becomes able to endure sunlight."""
    },
    {
        "id": "core-corps",
        "core": True,
        "tags": "corps corporacao cacadores demon slayer hashira kagaya ubuyashiki ranks mizunoto kinoe corvo selecao final",
        "text": """DEMON SLAYER CORPS — The Corps is led during most of the story by Kagaya Ubuyashiki. Regular ranks rise from Mizunoto through Mizunoe, Kanoto, Kanoe, Tsuchinoto, Tsuchinoe, Hinoto, Hinoe, Kinoto and Kinoe. Above ordinary ranks stand the Hashira, the elite swordsmen of the organization. Candidates usually train under a cultivator and survive the Final Selection on Mount Fujikasane before becoming official slayers. Members receive a uniform, a Nichirin weapon made from sunlight-absorbing ore and usually a Kasugai crow for mission delivery. Kakushi handle logistics, cleanup, transport and medical support."""
    },
    {
        "id": "core-breathing",
        "core": True,
        "tags": "respiracao breathing total concentration sun water flame thunder wind stone mist love serpent sound flower insect beast",
        "text": """BREATHING STYLES — Total Concentration Breathing uses controlled breathing to push a human body far beyond ordinary performance. Sun Breathing is the original style created by Yoriichi Tsugikuni. The major foundational derivatives are Water, Flame, Thunder, Wind and Stone; later branches include Mist, Love, Serpent, Sound, Flower and Insect, while Beast Breathing was developed independently by Inosuke from his own instincts. The visible water, flame, lightning and similar effects represent the style and sensation of techniques rather than ordinary elemental spellcasting. Skilled users can maintain Total Concentration Constant. Breathing does not make a human regenerate like a demon and still obeys the user's physical limits."""
    },
    {
        "id": "advanced-combat",
        "core": False,
        "tags": "marca demon slayer mark transparent world mundo transparente selfless state red blade lamina vermelha bright red",
        "text": """ADVANCED COMBAT STATES — Exceptional slayers can awaken a Demon Slayer Mark under extreme physical conditions, dramatically improving combat ability but carrying a severe historical cost. The Transparent World lets a fighter perceive internal motion such as muscles, blood flow and joints to read attacks with extraordinary precision. The Selfless State removes fighting spirit and hostile intent, making the user's presence harder to read. Nichirin blades can become bright red under particular conditions, interfering with demon regeneration. These abilities are rare and should never be treated as basic skills every slayer automatically possesses."""
    },
    {
        "id": "muzan-origin",
        "core": False,
        "tags": "muzan kibutsuji origem heian blue spider lily lirio aranha azul ubuyashiki",
        "text": """MUZAN'S ORIGIN — Muzan Kibutsuji lived more than a millennium before the main story and was born gravely ill. An experimental treatment involving the Blue Spider Lily transformed him into the first demon: physically powerful and long-lived, but unable to survive sunlight. His search for a body that can conquer the sun drives much of demon history. The Ubuyashiki family is distantly connected to his bloodline and suffers a hereditary curse; its leaders dedicate generations to destroying him and sustaining the Demon Slayer Corps."""
    },
    {
        "id": "yoriichi-history",
        "core": False,
        "tags": "yoriichi tsugikuni michikatsu kokushibo sun breathing hinokami kagura hanafuda brincos kamado historia",
        "text": """YORIICHI AND THE GOLDEN AGE — Yoriichi Tsugikuni was the greatest known swordsman and the creator of Sun Breathing. His twin brother Michikatsu could not equal him and eventually became the demon Kokushibo. Yoriichi once cornered Muzan and came closer than anyone to killing him, leaving Muzan permanently terrified of his technique and distinctive hanafuda earrings. Yoriichi later befriended the Kamado ancestors and passed on the forms and principles that the family preserved as the ceremonial Hinokami Kagura. Tanjiro eventually realizes this dance is connected to Sun Breathing."""
    },
    {
        "id": "kamado-beginning",
        "core": False,
        "tags": "tanjiro nezuko kamado familia giyu urokodaki monte sagiri sabito makomo final selection inicio",
        "text": """KAMADO BEGINNING — Tanjiro Kamado returns home to find his family slaughtered and Nezuko transformed into a demon. Giyu Tomioka initially intends to kill Nezuko but recognizes that she protects Tanjiro instead of eating him. He sends the siblings to Sakonji Urokodaki. Tanjiro trains on Mount Sagiri, receives guidance associated with Sabito and Makomo, and survives the Final Selection on Mount Fujikasane. His central goals become protecting Nezuko, finding a way to restore her humanity and defeating the source of demonkind."""
    },
    {
        "id": "early-arcs",
        "core": False,
        "tags": "swamp asakusa tamayo yushiro susamaru yahaba tsuzumi kyogai zenitsu inosuke early arcs",
        "text": """EARLY MISSIONS — Tanjiro's first missions establish how demons prey on civilians and how varied Blood Demon Arts can be. In Asakusa he encounters Muzan living under a human identity and meets Tamayo and Yushiro, demons who oppose Muzan. Tamayo researches demon biology and seeks samples from powerful demons. Tanjiro later meets Zenitsu Agatsuma and Inosuke Hashibira around the Tsuzumi Mansion incident, where the former Lower Rank demon Kyogai manipulates rooms with his drums. Tanjiro, Zenitsu and Inosuke gradually become the central field team around Nezuko."""
    },
    {
        "id": "natagumo",
        "core": False,
        "tags": "mount natagumo monte natagumo rui spider family shinobu giyu hinokami kagura lower five",
        "text": """MOUNT NATAGUMO — Rui, Lower Rank Five, builds a false spider family through fear and forced bonds. The mountain battle severely overwhelms ordinary slayers. Tanjiro first uses Hinokami Kagura in a desperate fight with Rui, while Nezuko manifests her Blood Demon Art. Giyu ultimately kills Rui, and Shinobu Kocho eliminates another spider demon with poison. The aftermath brings Tanjiro and Nezuko before the Hashira, forcing the Corps to decide whether Nezuko may be allowed to live. Kagaya supports the siblings under strict responsibility from Giyu and Urokodaki."""
    },
    {
        "id": "hashira-generation",
        "core": False,
        "tags": "hashira gyomei sanemi giyu rengoku kyojuro tengen muichiro mitsuri obanai shinobu pilares estilos",
        "text": """TAISHO HASHIRA — The principal Hashira are Gyomei Himejima (Stone), Sanemi Shinazugawa (Wind), Giyu Tomioka (Water), Kyojuro Rengoku (Flame), Tengen Uzui (Sound), Muichiro Tokito (Mist), Mitsuri Kanroji (Love), Obanai Iguro (Serpent) and Shinobu Kocho (Insect). They have very different temperaments and histories but serve the same organization. Gyomei is broadly regarded within the Corps as its strongest active Hashira. Shinobu relies on wisteria poison because she lacks the physical strength to decapitate demons. Hashira knowledge is not public knowledge, and even lower-ranked slayers do not automatically know every Hashira's private history."""
    },
    {
        "id": "twelve-kizuki",
        "core": False,
        "tags": "twelve kizuki doze luas demon moons upper lower kokushibo doma akaza hantengu gyokko gyutaro daki enmu rui nakime kaigaku",
        "text": """TWELVE KIZUKI — Muzan's elite demons are divided into six Upper Ranks and six Lower Ranks. The Upper Ranks are vastly more dangerous and had remained largely unchanged for generations before the main story. Key members are Kokushibo (Upper One), Doma (Upper Two), Akaza (Upper Three), Hantengu (Upper Four), Gyokko (Upper Five), and the shared Upper Six position of Gyutaro and Daki. Rui is Lower Five and Enmu is Lower One. After Rui's death, Muzan destroys most remaining Lower Ranks and leaves Enmu as the significant survivor. Later vacancies are filled by Nakime as Upper Four and Kaigaku as Upper Six."""
    },
    {
        "id": "mugen-train",
        "core": False,
        "tags": "mugen train trem infinito enmu rengoku akaza kyojuro dream sonho arco",
        "text": """MUGEN TRAIN — Enmu merges with the Mugen Train and traps passengers and slayers in dreams. Tanjiro, Nezuko, Zenitsu, Inosuke and Flame Hashira Kyojuro Rengoku protect the passengers and defeat Enmu. Immediately afterward, Upper Three Akaza attacks. Rengoku refuses Akaza's offer to become a demon and fights until dawn, dying from his wounds after ensuring the others survive. The event becomes a major emotional turning point for Tanjiro's group and demonstrates the gap between Hashira and the Upper Ranks."""
    },
    {
        "id": "entertainment-district",
        "core": False,
        "tags": "entertainment district yoshiwara distrito entretenimento tengen daki gyutaro zenitsu inosuke tanjiro nezuko",
        "text": """ENTERTAINMENT DISTRICT — Tengen Uzui investigates disappearances in Yoshiwara with Tanjiro, Zenitsu and Inosuke. Daki is exposed as a demon, but the true Upper Six threat also includes her brother Gyutaro; the siblings share the rank and must effectively be decapitated together. Nezuko displays a much stronger demon form and nearly loses control before Tanjiro calms her. After a brutal battle, the slayers defeat Gyutaro and Daki, breaking a century-long pattern of Upper Rank survival. Tengen loses an arm and an eye and retires from active Hashira duty, though he later assists the Corps."""
    },
    {
        "id": "swordsmith-village",
        "core": False,
        "tags": "swordsmith village vila ferreiros muichiro mitsuri genya hantengu gyokko nezuko sol yoriichi type zero",
        "text": """SWORDSMITH VILLAGE — Tanjiro travels to the hidden Swordsmith Village after damaging his sword. Muichiro Tokito, Mitsuri Kanroji and Genya Shinazugawa are also involved when Upper Five Gyokko and Upper Four Hantengu attack. Muichiro awakens a Demon Slayer Mark and defeats Gyokko. Hantengu divides into emotion-based bodies and ultimately manifests a powerful composite form; Mitsuri also awakens her mark while defending the village. Tanjiro, Nezuko and Genya help expose and destroy Hantengu's true body. At dawn Nezuko unexpectedly survives sunlight, making her Muzan's highest-priority target."""
    },
    {
        "id": "hashira-training",
        "core": False,
        "tags": "hashira training treinamento pilares mark kagaya muzan nakime infinity castle",
        "text": """HASHIRA TRAINING — With Nezuko hidden and Muzan preparing to move, the Corps begins an organization-wide Hashira Training program to raise the ability of regular slayers and help marked Hashira spread the conditions for awakening marks. Tanjiro trains under several Hashira and helps Giyu re-engage with the Corps. Nakime's eyes and familiars are used to locate members and facilities. Muzan eventually finds Kagaya Ubuyashiki. Kagaya deliberately sacrifices himself and his household in an explosion designed to trap and weaken Muzan long enough for Tamayo and the Hashira to attack. Nakime then pulls the combatants into the Infinity Castle."""
    },
    {
        "id": "infinity-castle",
        "core": False,
        "tags": "infinity castle castelo infinito shinobu doma kanao inosuke akaza giyu tanjiro zenitsu kaigaku kokushibo gyomei sanemi muichiro genya nakime",
        "text": """INFINITY CASTLE — The final battle fractures into simultaneous fights. Shinobu confronts Doma and allows him to absorb her after saturating her own body with a massive amount of wisteria poison; Kanao and Inosuke later exploit that sacrifice to defeat Doma. Zenitsu confronts Kaigaku, his former fellow student turned Upper Six, and kills him using a seventh Thunder Breathing form Zenitsu created himself. Tanjiro and Giyu fight Akaza; Akaza regains key human memories and ultimately ceases his own regeneration. Kokushibo battles Gyomei, Sanemi, Muichiro and Genya; Kokushibo is defeated, while Muichiro and Genya die from their wounds. Yushiro interferes with Nakime's control, and Muzan eventually kills Nakime rather than allow the castle to remain compromised."""
    },
    {
        "id": "sunrise-countdown",
        "core": False,
        "tags": "sunrise countdown muzan final battle tamayo drug poison aging tanjiro demon king nezuko human kanao ending",
        "text": """SUNRISE COUNTDOWN — After the Infinity Castle collapses, the survivors hold Muzan above ground until sunrise. Tamayo's multi-stage drug is crucial: it attacks Muzan's condition in several ways, including forcing humanization effects, rapid aging and reduced ability to divide or escape. Numerous slayers and support members are killed or maimed during the battle. Obanai and Mitsuri die after the fight; Gyomei also dies from his injuries. Muzan is destroyed by sunlight, but before disappearing he transfers his cells and will into Tanjiro, briefly turning him into an extraordinarily dangerous demon able to endure the sun. Kanao uses the remaining human-restoration medicine, aided by Tanjiro's bonds and resistance, and Tanjiro returns to being human. Nezuko has already been restored to humanity through Tamayo's treatment."""
    },
    {
        "id": "ending",
        "core": False,
        "tags": "ending epilogue descendants reincarnation modern japan end corps disbanded yushiro",
        "text": """AFTERMATH — Muzan's death ends the central demon threat and the Demon Slayer Corps no longer needs to continue its old mission. Surviving characters carry permanent physical and emotional consequences. Yushiro remains as a surviving demon who had opposed Muzan. The manga's epilogue jumps to modern Japan and shows descendants and reincarnation-like counterparts of many characters living peaceful ordinary lives, emphasizing that the sacrifices of the Taisho generation created a future no longer dominated by Muzan."""
    },
    {
        "id": "tamayo-medicine",
        "core": False,
        "tags": "tamayo yushiro medicine medicina nezuko cure human drug muzan shinobu poison research",
        "text": """TAMAYO'S RESEARCH — Tamayo is a demon physician who escaped Muzan's control and refuses to hunt humans in the ordinary way. With Yushiro she researches demon blood and works toward reversing demon transformation. Samples gathered from powerful demons help her work. Her cooperation with Shinobu becomes decisive in the final battle: their medical and poison knowledge creates treatments for Nezuko and Tanjiro and the drug combination used against Muzan. This research is highly secret; an average Corps member or civilian should not automatically know its details."""
    },
    {
        "id": "genya",
        "core": False,
        "tags": "genya shinazugawa demon eating eats flesh gun nichirin kokushibo",
        "text": """GENYA'S ABILITY — Genya Shinazugawa cannot use a normal Breathing Style. Instead, his unusual digestive system lets him temporarily gain demon-like physical traits and sometimes aspects of a demon's ability by consuming demon flesh. He also fights with a Nichirin firearm and blade. This is rare, dangerous and not a general technique available to other slayers. During the Kokushibo battle his ability becomes tactically important, but he is fatally wounded."""
    },
    {
        "id": "nichirin-tools",
        "core": False,
        "tags": "nichirin sword espada blade ore minério color red poison wisteria weapon chains gun",
        "text": """NICHIRIN AND WEAPONS — Nichirin weapons are forged from special ore exposed to sunlight. Most slayers use swords, but weapons vary with the fighter: Gyomei uses a chained axe-and-flail arrangement, Mitsuri uses a flexible whip-like sword, Tengen uses paired cleavers, Shinobu uses a specialized thrusting blade for poison delivery, and Genya uses a Nichirin firearm alongside a short blade. Blade color can reflect the wielder. Bright red Nichirin is a separate advanced state and should not be confused with ordinary blade coloration."""
    },
    {
        "id": "locations",
        "core": False,
        "tags": "locations locais mount kumotori sagiri fujikasane asakusa tsuzumi natagumo butterfly mansion yoshiwara swordsmith village ubuyashiki infinity castle",
        "text": """IMPORTANT LOCATIONS — Mount Kumotori is associated with the Kamado family's home; Mount Sagiri with Urokodaki's training; Mount Fujikasane with Final Selection and year-round wisteria; Asakusa with Tanjiro's early encounter with Muzan and Tamayo; Tsuzumi Mansion with Kyogai; Mount Natagumo with Rui's spider family; the Butterfly Mansion with recovery and rehabilitation; Yoshiwara with the Entertainment District battle; the Swordsmith Village with hidden Nichirin craftsmen; the Ubuyashiki estate with Corps leadership; and the Infinity Castle with Muzan's shifting extradimensional stronghold controlled for much of the story by Nakime. Secret locations should not be casually known by civilians or unrelated NPCs."""
    },
    {
        "id": "knowledge-rules",
        "core": True,
        "tags": "knowledge secrets npc roleplay canon spoilers common knowledge meta lore",
        "text": """ROLEPLAY KNOWLEDGE RULE — This reference is author/GM knowledge, not automatic character knowledge. A civilian generally does not know that demons or the Corps are real. A low-ranked slayer may know Corps basics but not private Hashira history, Muzan's origin, Upper Rank identities, secret villages, Tamayo's research or final-battle facts unless the campaign timeline and that character's memories justify it. A demon may know more about Muzan and the Kizuki, but still should not know information it never learned. Use the campaign date, NPC profile, current events, conversation history and stored memories to decide what the character can actually say."""
    },
    {
        "id": "custom-rp",
        "core": True,
        "tags": "oc custom character original chamas sangue breathing hybrid half demon oni canon override",
        "text": """CUSTOM RP COMPATIBILITY — The campaign may include original characters, original Breathing Styles, alternate events or other user-created material. Treat official Demon Slayer canon as the baseline world model, but treat explicit campaign facts and stored memories as authoritative for this RP when they intentionally diverge. Do not erase an OC concept merely because it is absent from official canon. Do not silently rewrite established canon either: when a custom rule changes canon, preserve that change consistently from then on."""
    },
]


_STOP = {
    "a","o","as","os","de","da","do","das","dos","e","em","um","uma","para","por","com","que","se",
    "the","of","and","to","in","is","on","for","an","this","that","um","uma","no","na","nos","nas"
}


def _norm(text):
    text = unicodedata.normalize("NFKD", str(text or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    return re.findall(r"[a-z0-9]+", text)


def _tokens(text):
    return {x for x in _norm(text) if len(x) > 2 and x not in _STOP}


def is_demon_slayer_campaign(campaign):
    hay = " ".join(_norm((campaign or {}).get("name", "") + " " + (campaign or {}).get("premise", "")))
    return "demon slayer" in hay or "kimetsu" in hay


def select_lore(campaign, npc=None, location=None, message="", limit_chars=5200):
    """Return the most relevant Demon Slayer canon chunks for one turn.

    The selection is deliberately local and deterministic: no external service, no
    embedding requirement, and no character entities are created in the campaign.
    """
    if limit_chars <= 0 or not is_demon_slayer_campaign(campaign):
        return ""

    npc = npc or {}
    location = location or {}
    query = " ".join([
        (campaign or {}).get("name", ""),
        (campaign or {}).get("premise", ""),
        npc.get("name", ""),
        npc.get("profile", ""),
        npc.get("mood", ""),
        " ".join(npc.get("goals", []) if isinstance(npc.get("goals"), list) else []),
        location.get("name", ""),
        location.get("description", ""),
        message or "",
    ])
    q = _tokens(query)

    ranked = []
    for index, chunk in enumerate(DEMON_SLAYER_LORE):
        keys = _tokens(chunk["id"] + " " + chunk.get("tags", "") + " " + chunk["text"])
        overlap = len(q & keys)
        # Title/tags matter more than incidental words inside the paragraph.
        tag_overlap = len(q & _tokens(chunk["id"] + " " + chunk.get("tags", "")))
        score = tag_overlap * 5 + overlap
        ranked.append((score, -index, chunk))

    chosen = [c for c in DEMON_SLAYER_LORE if c.get("core")]
    seen = {c["id"] for c in chosen}
    for _, _, chunk in sorted(ranked, reverse=True):
        if chunk["id"] not in seen:
            chosen.append(chunk)
            seen.add(chunk["id"])

    parts = []
    used = 0
    for chunk in chosen:
        part = f"[{chunk['id']}] {chunk['text'].strip()}"
        extra = len(part) + (2 if parts else 0)
        if used + extra > limit_chars:
            continue
        parts.append(part)
        used += extra
    return "\n\n".join(parts)
