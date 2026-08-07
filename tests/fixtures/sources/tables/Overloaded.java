package content.global.skill.construction;

public enum Overloaded {

	CURTAINS       (13570, true),
	BASIC_WINDOW   (13099, -1, 1, 0),
	PORTAL         (13615, 8173, 5, 31, new Item[] { new Item(Items.OAK_PLANK_8778, 2) }),
	SHUTTERED      (new int[] { 13253, 13226, 13235 }, 8076, 49, 228, new Item[] { new Item(Items.PLANK_960, 8) }),
	DEAD_TREE      (13411, 8173, 5, 31, new int[] { BuildingUtils.WATERING_CAN }, new Item[] { new Item(Items.BAGGED_DEAD_TREE_8417) }),
	MITHRIL_ARMOUR (13491, 8270, 28, 135, new Item[] { new Item(Items.OAK_PLANK_8778, 2) }, new Item[] { new Item(Items.MITHRIL_FULL_HELM_1159, 1) }),
	GLORY_MOUNT    (13523, 8283, 47, 290, new Item[] { new Item(Items.TEAK_PLANK_8780, 3) }, new Item[] { new Item(Items.AMULET_OF_GLORY_1704) }, new String[] { "Teak plank: 3", "Amulet of Glory" }),
	NOTICE_BOARD   ("Notice board", 11, new String[] { "Easy", "Medium" }, new String[][] { { "Pick 5 bananas" }, { "Kill a lesser demon" } });

	Overloaded(int objectId, boolean invisibleNode) {
	}

	Overloaded(int objectId, int interfaceItem, int level, int experience) {
	}

	Overloaded(int objectId, int interfaceItem, int level, int experience, Item[] items) {
	}

	Overloaded(int[] objectIds, int interfaceItem, int level, int experience, Item[] items) {
	}

	Overloaded(int objectId, int interfaceItem, int level, int experience, int[] tools, Item[] items) {
	}

	Overloaded(int objectId, int interfaceItem, int level, int experience, Item[] items, Item[] refundItems) {
	}

	Overloaded(int objectId, int interfaceItem, int level, int experience, Item[] items, Item[] refundItems, String[] reqsText) {
	}

	Overloaded(String name, int child, String[] levelNames, String[][] achievements) {
	}
}
