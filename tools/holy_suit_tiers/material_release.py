"""Exact authored material presentation released before the distinct material icons.

Keep these predecessor identities frozen: they admit only the reviewed forward
upgrade, without accepting arbitrary content occupying a newly allocated key.
"""

PREVIOUS_MATERIAL_ATLAS_SHA256 = "2a3a6baf08c39b8756f5cdc6428e818feeb61df1c71ad2b953f3613ded8c9c83"
DISTINCT_MATERIAL_ATLAS_SHA256 = "43737baaa1a2c71a96da3c511162f705edbeb7fc9c6691a1957b73a5014a3a9a"
PREVIOUS_MATERIAL_ATLAS_RELEASES = frozenset((
    PREVIOUS_MATERIAL_ATLAS_SHA256, DISTINCT_MATERIAL_ATLAS_SHA256))
PREVIOUS_DIVINIUM_NAME = "Divinium Ware"
PREVIOUS_DIVINIUM_DESCRIPTION = (
    "The Master Vestment Forger uses Divinium Ware to advance Level 10 Seraphite "
    "equipment into Divinium and upgrade Divinium Levels 1-10. "
    "The target level determines the ware quantity. Experience Prisms are required when specified.")
PREVIOUS_DIVINIUM_HELP = '''HelpSystem_Cofig["RebornHolySuitDivinium"] = {
  static_text=[[
|cFFFFF8E7Divinium Suit|cFFFFFFFF

Divinium increases supported base equipment attributes by 71%-90% across ten levels.
Holy Suit bonus percentages by level:
1: 71%, 2: 73%, 3: 75%, 4: 77%, 5: 79%, 6: 82%, 7: 84%, 8: 86%, 9: 88%, 10: 90%

Level 10 Seraphite -> Level 1 Divinium: 99 Experience Prisms + 1 Divinium Ware.
Level 1-2: 102 Experience Prisms + 2 Divinium Ware.
Level 2-3: 105 Experience Prisms + 3 Divinium Ware.
Level 3-4: 108 Experience Prisms + 4 Divinium Ware.
Level 4-5: 111 Experience Prisms + 5 Divinium Ware.
Level 5-6: 114 Experience Prisms + 6 Divinium Ware.
Level 6-7: 117 Experience Prisms + 7 Divinium Ware.
Level 7-8: 120 Experience Prisms + 8 Divinium Ware.
Level 8-9: 123 Experience Prisms + 9 Divinium Ware.
Level 9-10: 126 Experience Prisms + 10 Divinium Ware.
Level 10 is the maximum. Appended attributes and Class Suit bonuses are separate.
  ]]
}'''
