class HorseStatus:
    Normal = "正常"
    Slowness = "减速"
    SpeedUp = "加速"
    Freeze = "冻结"
    Dizziness = "眩晕"
    Death = "死亡"
    Shield = "护盾"
    Poisoning = "中毒"


props = {
    # 道具名            描述          值 持续回合 概率
    "香蕉皮": (HorseStatus.Dizziness, 0, 1, 7),
    "肥皂": (HorseStatus.Slowness, 0.5, 2, 10),
    "冰弹": (HorseStatus.Freeze, 0, 3, 2),
    "苹果": (HorseStatus.SpeedUp, 1.2, 1, 20),
    "烂苹果": (HorseStatus.Poisoning, 1, 12, 5),
    "兴奋剂": (HorseStatus.SpeedUp, 1.5, 2, 3),
    "强效兴奋剂": (HorseStatus.SpeedUp, 2, 3, 1),
    "马蹄铁": (HorseStatus.Shield, 1, 3, 3),
    "高级马蹄铁": (HorseStatus.Shield, 1, 5, 1),
    "炸弹": (HorseStatus.Death, 0, 1, 1),
    "毒药": (HorseStatus.Poisoning, 1, 8, 1),
}
