import sqlite3
import csv
import time
import scrython
import copy
import base64


class DBField(object):
    def __init__(self, name, title, type, field_name = None):
        self._name = name
        if field_name:
            self._field_name = field_name
        else:
            self._field_name = name
        self._title = title
        self._type = type
        self._value = None
        self._is_dirty = False


    def name(self):
        return self._name


    def fieldName(self):
        return self._field_name


    def type(self):
        return self._type


    def title(self):
        return self._title


    def value(self):
        return self._value


    def setValue(self, value):
        if self._value == value:
            return False

        self._value = value
        self._is_dirty = True
        return True


    def setSqlValue(self, value):
        if self._type in [list, dict]:
            self._value = self.decodeValue(value)
        elif self._type == bool:
            self._value = (value == 1)
        else:
            self._value = value


    def isEmpty(self):
        return not self._value


    def sqlValue(self):
        if not self._value:
            return  "''"

        if self._type == bool:
            if self._value:
                return 1
            else:
                return 0
        elif self._type == str:
            return "\"{}\"".format(self.value().replace("\"", ''))
        elif self._type in [list, dict]:
            return "\"{}\"".format(self.encodeValue(self.value()))
        else:
            return self.value()


    def sqlUpdateExp(self):
        return "{} = {}".format(self.fieldName(), self.sqlValue())


    def encodeValue(self, value):
        str_value = str(value)
        bytes = str_value.encode()
        base64_bytes = base64.urlsafe_b64encode(bytes)
        return base64_bytes.decode()


    def decodeValue(Self, value):
        if not value:
            return value
        value_bytes = base64.urlsafe_b64decode(value)
        decoded = value_bytes.decode()
        return eval(decoded)


class CardFaceFiled(DBField):
    def __init__(self, name, title):
        super().__init__(name, title, str)


class DBTable(object):
    def __init__(self, db, name, fields):
        self._db = db
        self._name = name
        self._fields = [DBField("id", "Id", int)] + fields


    def value(self, name):
        return self._data[name]


    def setValue(self, name, value):
        self._data[name] = value


    def fields(self):
        return self._fields


    def fieldNames(self):
        names = []
        for field in self._fields:
            names.append(field.fieldName())
        return names


    def fieldByTitle(self, title):
        for field in self._fields:
            if field.title() == title:
                return field
        return None


    def fieldByFieldName(self, field_name):
        for field in self._fields:
            if field.fieldName() == field_name:
                return field
        return None

    def exists(self):
        table_name = self._name
        cur = self._db.cursor()
        res = cur.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
        return (not res.fetchone() is None)


    def createTable(self):
        if self.exists():
            return

        field_names = self.fieldNames()
        del field_names[0] # delete id field
        columns = ','.join(field_names)
        table_name = self._name
        cur = self._db.cursor()
        cur.execute(f"CREATE TABLE {table_name} (id INTEGER PRIMARY KEY ASC, {columns})")


    def list(self, where):
        filter = ""
        if where:
            filter = f"where {where}"
        table_name = self._name
        rows = []
        for row in self._db.execute(f"SELECT * FROM {table_name} {filter}"):
            rows.append(self.parseRow(row))

        if len(rows) == 0:
            return None
        return rows


    def emptyField(self, fieldName):
        for field in self._fields:
            if field.fieldName() == fieldName:
                return copy.deepcopy(field)
        return None


    def parseRow(self, row):
        data = {}
        for key, value in row.items():
            field = self.emptyField(key)
            field.setSqlValue(value)
            data[field.fieldName()] = field

        return data


    def addRow(self):
        row = {}
        for field in self._fields:
            row[field.name()] = copy.deepcopy(field)
        return row


    def commit(self, row):
        if not row["id"].isEmpty():
            print("Will update table")
            self.update(row["id"].sqlValue(), row)
        else:
            print("Will insert values")
            self.insert(row)
        self._db.commit()
        return True


    def update(self, id, row):
        field_to_update = []
        for key, field in row.items():
            if not field._is_dirty:
                continue
            field_to_update.append(field.sqlUpdateExp())

        if len(field_to_update) == 0:
            return

        table_name = self._name
        db_update_cmd = ", ".join(field_to_update)
        cur = self._db.cursor()
        cur.execute(f"UPDATE {table_name} SET {db_update_cmd} WHERE id = {id}")


    def insert(self, row):
        field_names = []
        values = None

        for field in self._fields:
            if field.fieldName() == "id":
                continue
            field_names.append(field.fieldName())
            field_to_update = row[field.name()]
            if field_to_update:
                if values:
                    values = values + ", "
                else:
                    values = ""
                values = values + "{}".format(field_to_update.sqlValue())
            else:
                values.append(0)

        table_name = self._name
        field_names_str = ", ".join(field_names)

        cur = self._db.cursor()
        cmd = f"INSERT INTO {table_name} ({field_names_str}) VALUES({values})"
        print("cmd:", cmd)
        cur.execute(cmd)


class CardSetDB(DBTable):
    def __init__(self, db):
        fields = [
            DBField("code", "Code", str),
            DBField("mtgo_code", "MTGO Code", str),
            DBField("arena_code", "Arena Code", str),
            DBField("tcgplayer_id", "TCGplayer’s Id", int),
            DBField("name", "Name", str),
            DBField("set_type", "Set Type", str),
            DBField("released_at", "Release Date", str),
            DBField("block_code", "Block Code", str),
            DBField("block", "Block", str),
            DBField("parent_set_code", "Parent Set Code", str),
            DBField("card_count", "Card Count", int),
            DBField("printed_size", "Printed Size", int),
            DBField("digital", "Digital", bool),
            DBField("foil_only", "Foil Only", bool),
            DBField("nonfoil_only", "Non Foil Only", bool),
            DBField("scryfall_uri", "ScryFall Uri", str),
            DBField("uri", "Uri", str),
            DBField("icon_svg_uri", "Icon", str),
            DBField("search_uri", "Search Uri", str)
        ]
        super().__init__(db, "card_sets", fields)


class CardDB(DBTable):
    def __init__(self, db):
        #COLUMNS  = ["id", "name", "uri", "limited_tier", "constructed_tier", "Seen_ext", "ALSA_ext", "Picked_ext", "ATA_ext", "GP_ext", "GP_Percent_ext", "GP_WR_ext", "OH_ext", "OH_WR_ext", "GD_ext", "GD_WR_ext", "GIH_ext", "GIH_WR_ext", "GNS_ext", "GNS_WR_ext", "IWD_ext"]
        #COLUMNS_TITLE  = ["Id", "Name", "Uri", "Lim. T.", "Const. T.", "# Seen", "ALSA", "# Picked", "ATA", "# GP", "% GP", "GP WR", "# OH", "OH WR", "# GD", "GD WR", "# GIH", "GIH WR", "# GNS", "GNS WR", "IWD"]

        fields = [
            #Core Card Fields
            DBField("scryfall_id", "Scryfall Id", str),
            DBField("arena_id", "Arena Id", int),
            DBField("lang", "lang", str),
            DBField("mtgo_id", "MTGO Id", int),
            DBField("mtgo_foil_id", "MTGO Foil Id", int),
            DBField("multiverse_ids", "Multiverse Ids", list),
            DBField("tcgplayer_id", "TCGplayer’s Id", int),
            DBField("tcgplayer_etched_id", "TCGplayer’s Etched Id", int),
            DBField("cardmarket_id", "CardMarket Id", int),
            DBField("layout", "Layout", str),
            DBField("oracle_id", "Oracle Id", str),
            DBField("prints_search_uri", "Prints Search Uri", str),
            DBField("rulings_uri", "Rulings Uri", str),
            DBField("scryfall_uri", "ScryFall Uri", str),
            DBField("uri", "Uri", str),

            # Gameplay Fields
            DBField("all_parts", "All Pars", list),
            #DBField("card_faces", "Card Faces", list),
            DBField("cmc", "Card Mana Value", float),
            DBField("color_identity", "Color IdentiTy", list),
            DBField("color_indicator", "Color Indicator", list),
            DBField("colors", "Colors", list),
            DBField("defense", "Defense", str),
            DBField("edhrec_rank", "EDHREC Rank", int),
            DBField("hand_modifier", "Hand Modifier", str),
            DBField("keywords", "Keywords", list),
            DBField("legalities", "Legalities", dict),
            DBField("life_modifier", "Life Modifier", str),
            DBField("loyalty", "Loyalty", str),
            DBField("mana_cost", "Mana Cost", str),
            DBField("name", "Name", str),
            DBField("oracle_text", "Oracle Text", str),
            DBField("penny_rank", "Penny Rank", int),
            DBField("power", "Power", str),
            DBField("produced_mana", "Produced Mana", list),
            DBField("reserved", "Reserved", bool),
            DBField("toughness", "Toughness", str),
            DBField("type_line", "Type Line", str),

            # Print Fields
            DBField("artist", "Artist", str),
            DBField("artist_ids", "Artist ids", list),
            DBField("attraction_lights", "Attraction Lights", list),
            DBField("booster", "Booster", bool),
            DBField("border_color", "Border Color", str),
            DBField("card_back_id", "Card Back Id", str),
            DBField("collector_number", "Collector Number", str),
            DBField("content_warning", "Content Warning", bool),
            DBField("digital", "Digital", bool),
            DBField("finishes", "Finishes", list),
            DBField("flavor_name", "Flavor Name", str),
            DBField("flavor_text", "Flavor Text", str),
            DBField("frame_effects", "Frame Effects", list),
            DBField("frame", "Frame", str),
            DBField("full_art", "Full Art", bool),
            DBField("games", "Games", list),
            DBField("highres_image", "Highres Image", bool),
            DBField("illustration_id", "Illustration Id", str),
            DBField("image_status", "Image Status", str),
            DBField("image_uris", "Image Uris", dict),
            DBField("oversized", "oversized", bool),
            DBField("prices", "Prices", dict),
            DBField("printed_name", "Printed Name", str),
            DBField("printed_text", "Printed Text", str),
            DBField("printed_type_line", "Printed Type Line", str),
            DBField("promo", "Promo", bool),
            DBField("promo_types", "Promo Types", list),
            DBField("purchase_uris", "Purchase Uris", dict),
            DBField("rarity", "Rarity", str),
            DBField("related_uris", "Related Uris", dict),
            DBField("released_at", "Release Date", str),
            DBField("reprint", "Reprint", bool),
            DBField("scryfall_set_uri", "Scryfall Set Uri", str),
            DBField("set_name", "Set Name", str),
            DBField("set_search_uri", "Set Sarch Uri", str),
            DBField("set_type", "Set Type", str),
            DBField("set_uri", "Set Uri", str),
            DBField("set", "Set", str, "set_"),
            DBField("set_id", "Set Id", str),
            DBField("story_spotlight", "Story Spotlight", bool),
            DBField("textless", "Textless", bool),
            DBField("variation", "Variation", bool),
            DBField("variation_of", "Variation Of", str),
            DBField("security_stamp", "Security Stamp", str),
            DBField("watermark", "Watermark", str),
            DBField("preview.previewed_at", "Preview At", str, "preview_previewed_at"),
            DBField("preview.source_uri", "Preview Uri", str, "preview_source_uri"),
            DBField("preview.source", "Preview Source", str, "preview_source")
        ]
        super().__init__(db, "cards", fields)


    def downloadSet(self, set_name):
        page_count = 1
        while True:
            time.sleep(0.5)
            page = scrython.cards.Search(q="e:{}".format(set_name), page=page_count)
            for card in page.data():
                scryfall_id = card["id"]
                current_data = self.list("scryfall_id = \"{}\"".format(scryfall_id))
                if current_data:
                    current_data = current_data[0]
                else:
                    current_data = self.addRow()
                    current_data["scryfall_id"].setValue(scryfall_id)

                for card_field, card_value in card.items():
                    if card_field == "id":
                        continue
                    if not card_field in current_data:
                        print("Skip field:", card_field)
                        continue

                    field = current_data[card_field]
                    field.setValue(card_value)

                self.commit(current_data)

            page_count += 1
            if not page.has_more():
                break


class SevenTeenLandsCardDB(DBTable):
    def __init__(self, db):
        fields = [
            DBField("card_id", "Card Id", int),
            DBField("card_set", "Card Set", str),
            DBField("name", "Name", str),
            DBField("color", "Color", str),
            DBField("rarity", "Rarity", str),
            DBField("seen", "# Seen", int),
            DBField("alsa", "ALSA", float),
            DBField("picked", "# Picked", int),
            DBField("ata", "ATA", float),
            DBField("gp", "# GP", int),
            DBField("gp_p", "% GP", float),
            DBField("gp_wr", "GP WR", float),
            DBField("oh", "# OH", int),
            DBField("oh_wr", "OH WR", float),
            DBField("gd", "# GD", int),
            DBField("gd_wr", "GD WR", float),
            DBField("gih", "# GIH", int),
            DBField("gih_wr", "GIH WR", float),
            DBField("gns", "# GNS", int),
            DBField("gns_wr", "GNS WR", float),
            DBField("iwd", "IWD", float)
        ]
        super().__init__(db, "seventeen_lands", fields)


    def importFromFile(self, card_set, filename):
        def fieldByTitle(fields, title):
            for key, field in fields.items():
                if field.title() == title:
                    return key
            return None

        card_db = CardDB(self._db)
        with open(filename, newline='') as csvfile:
            reader = csv.DictReader(csvfile, delimiter=',', quotechar='"')
            for row in reader:
                card_name = row["Name"]
                found = card_db.list(f"set_ = '{card_set}' AND name LIKE \"{card_name}%\"")
                if not found:
                    print(f"Failed to import card {card_name}. Card does not exists on database. Fir set {card_set}", found)
                    continue
                if len(found) != 1:
                    print(f"Multiple cards found for: {card_name}")
                    continue

                found = found[0]
                card_id = found["id"].sqlValue()
                current_data = self.list(f"card_id = {card_id}")
                if not current_data:
                    current_data = self.addRow()
                    current_data["card_id"].setValue(card_id)
                    current_data["card_set"].setValue(card_set)
                else:
                    current_data = current_data[0]

                for key, value in row.items():
                    field_name = fieldByTitle(current_data, key)
                    if not field_name:
                        print("Invalid field on file",  key)
                        continue

                    if type(value) == str:
                        value = value.replace("%", "").strip()
                        if key == "IWD":
                            value = value.replace("pp", "")

                    current_data[field_name].setValue(value)

                self.commit(current_data)


class UserFieldsDB(DBTable):
    def __init__(self, db):
        fields = [
            DBField("card_id", "Card Id", int),
            DBField("limited_tier", "Limited Tier", str),
            DBField("constructed_tier", "Constructed Tier", str),
        ]
        super().__init__(db, "user_fields", fields)


def createDatabase(filename):
    db = None
    try:
        db = sqlite3.connect(filename)
    except:
        print("Failed to open database:", filename)
        return None

    def dict_factory(cursor, row):
        fields = [column[0] for column in cursor.description]
        return {key: value for key, value in zip(fields, row)}

    db.row_factory = dict_factory
    CardSetDB(db).createTable()
    CardDB(db).createTable()
    SevenTeenLandsCardDB(db).createTable()
    UserFieldsDB(db).createTable()
    return db
