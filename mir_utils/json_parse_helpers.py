import dataclasses

class JsonParseHelper:

    @staticmethod
    def to_dict(obj):
        # 1) Dataclass → dict récursif
        if dataclasses.is_dataclass(obj):
            return {k: JsonParseHelper.to_dict(v) for k, v in dataclasses.asdict(obj).items()}
        # 2) Dictionnaire
        elif isinstance(obj, dict):
            return {k: JsonParseHelper.to_dict(v) for k, v in obj.items()}
        # 3) Liste ou tuple → liste JSON
        elif isinstance(obj, (list, tuple)):
            return [JsonParseHelper.to_dict(v) for v in obj]
        # 4) Type Python (float, int, bool…) → nom du type
        elif isinstance(obj, type):
            return obj.__name__
        # 5) Enum
        elif hasattr(obj, 'value'):
            return obj.value

        # Path (exemple si type non géré)
        # elif isinstance(obj, Path):
        #     return str(obj)

        # 6) Valeur simple
        return obj

    #utilisé pour désérialiser les dictionnaires [str, Any] car le Any ne sera pas gérable par dacite
    @staticmethod
    def decode_value(v):
        # Reconversion des types
        if v == "float":
            return float
        if v == "int":
            return int
        if v == "bool":
            return bool
        # Listes → tuples si tu veux retrouver la forme originale
        if isinstance(v, list):
            return tuple(JsonParseHelper.decode_value(x) for x in v)
        return v
        