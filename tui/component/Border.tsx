const BASE = {
  topT: " ",
  bottomT: " ",
  leftT: " ",
  rightT: " ",
  cross: " ",
};

export const SplitBorder = {
  customBorderChars: {
    topLeft: "┃",
    topRight: " ",
    bottomLeft: "┃",
    bottomRight: " ",
    horizontal: " ",
    vertical: "┃",
    ...BASE,
  },
};

export const EmptyBorder = {
  topLeft: " ",
  topRight: " ",
  bottomLeft: " ",
  bottomRight: " ",
  horizontal: " ",
  vertical: " ",
  ...BASE,
};
