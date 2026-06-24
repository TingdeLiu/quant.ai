/* @ds-bundle: {"format":3,"namespace":"ClaudeDesignSystem_9a1625","components":[{"name":"Avatar","sourcePath":"components/core/Avatar.jsx"},{"name":"Badge","sourcePath":"components/core/Badge.jsx"},{"name":"Button","sourcePath":"components/core/Button.jsx"},{"name":"Card","sourcePath":"components/core/Card.jsx"},{"name":"Checkbox","sourcePath":"components/core/Checkbox.jsx"},{"name":"Dialog","sourcePath":"components/core/Dialog.jsx"},{"name":"IconButton","sourcePath":"components/core/IconButton.jsx"},{"name":"Input","sourcePath":"components/core/Input.jsx"},{"name":"Radio","sourcePath":"components/core/Radio.jsx"},{"name":"Select","sourcePath":"components/core/Select.jsx"},{"name":"Switch","sourcePath":"components/core/Switch.jsx"},{"name":"Tabs","sourcePath":"components/core/Tabs.jsx"},{"name":"Tag","sourcePath":"components/core/Tag.jsx"},{"name":"Textarea","sourcePath":"components/core/Textarea.jsx"},{"name":"Tooltip","sourcePath":"components/core/Tooltip.jsx"}],"sourceHashes":{"components/core/Avatar.jsx":"f49d73590fad","components/core/Badge.jsx":"eea54bc15778","components/core/Button.jsx":"e37f46ada7ed","components/core/Card.jsx":"1e886954c1d5","components/core/Checkbox.jsx":"1d4185afcb95","components/core/Dialog.jsx":"ef069ae9bbdd","components/core/IconButton.jsx":"0b4e3c624f0c","components/core/Input.jsx":"2f2182e739ef","components/core/Radio.jsx":"bd78038ce10e","components/core/Select.jsx":"25a5505049d0","components/core/Switch.jsx":"07e6d9408d5d","components/core/Tabs.jsx":"7d647fff5007","components/core/Tag.jsx":"fa40d162a4c8","components/core/Textarea.jsx":"a8b7dcea1766","components/core/Tooltip.jsx":"588d024530e5","ui_kits/markets/app.jsx":"c0148e2847c6","ui_kits/markets/chrome.jsx":"db63a22283b8","ui_kits/worldforge/app.jsx":"8ab26c6b8fc9","ui_kits/worldforge/image-slot.js":"9309434cb09c"},"inlinedExternals":[],"unexposedExports":[]} */

(() => {

const __ds_ns = (window.ClaudeDesignSystem_9a1625 = window.ClaudeDesignSystem_9a1625 || {});

const __ds_scope = {};

(__ds_ns.__errors = __ds_ns.__errors || []);

// components/core/Avatar.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Avatar — user/model identity. Image, initials, or the Tyndall burst mark.
 */
const AVATAR_SIZES = {
  xs: 24,
  sm: 28,
  md: 36,
  lg: 44,
  xl: 56
};
function Avatar({
  src,
  name = "",
  brand = false,
  size = 36,
  style = {},
  ...rest
}) {
  if (typeof size === "string") size = AVATAR_SIZES[size] || 36;
  const initials = name.split(" ").map(w => w[0]).filter(Boolean).slice(0, 2).join("").toUpperCase();
  const base = {
    width: size,
    height: size,
    borderRadius: "50%",
    flex: "none",
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
    fontFamily: "var(--font-body)",
    fontWeight: 600,
    fontSize: Math.round(size * 0.4),
    userSelect: "none",
    ...style
  };
  if (brand) {
    return /*#__PURE__*/React.createElement("span", _extends({
      style: {
        ...base,
        background: "var(--clay-50)",
        border: "1px solid var(--clay-100)"
      }
    }, rest), /*#__PURE__*/React.createElement("span", {
      style: {
        width: size * 0.62,
        height: size * 0.62,
        background: "var(--clay-400)",
        WebkitMaskImage: "radial-gradient(circle, #000 60%, transparent 61%)",
        borderRadius: "50%"
      }
    }));
  }
  if (src) {
    return /*#__PURE__*/React.createElement("img", _extends({
      src: src,
      alt: name,
      style: {
        ...base,
        objectFit: "cover"
      }
    }, rest));
  }
  return /*#__PURE__*/React.createElement("span", _extends({
    style: {
      ...base,
      background: "var(--kraft-200)",
      color: "var(--kraft-700)"
    }
  }, rest), initials || "?");
}
Object.assign(__ds_scope, { Avatar });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Avatar.jsx", error: String((e && e.message) || e) }); }

// components/core/Badge.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Badge — small status / category label. Subtle warm fills, muted semantics.
 */
function Badge({
  children,
  variant = "neutral",
  tone,
  size = "md",
  dot = false,
  style = {},
  ...rest
}) {
  variant = tone || variant; // `tone` accepted as an alias
  const palettes = {
    neutral: {
      bg: "var(--kraft-100)",
      fg: "var(--kraft-700)",
      dot: "var(--kraft-500)"
    },
    accent: {
      bg: "var(--clay-50)",
      fg: "var(--clay-700)",
      dot: "var(--clay-400)"
    },
    success: {
      bg: "var(--status-success-bg)",
      fg: "var(--status-success)",
      dot: "var(--status-success)"
    },
    warning: {
      bg: "var(--status-warning-bg)",
      fg: "var(--status-warning)",
      dot: "var(--status-warning)"
    },
    danger: {
      bg: "var(--status-danger-bg)",
      fg: "var(--status-danger)",
      dot: "var(--status-danger)"
    },
    info: {
      bg: "var(--status-info-bg)",
      fg: "var(--status-info)",
      dot: "var(--status-info)"
    }
  };
  const p = palettes[variant] || palettes.neutral;
  const sizes = {
    sm: {
      fontSize: 11,
      padding: "2px 7px"
    },
    md: {
      fontSize: 12,
      padding: "3px 9px"
    }
  };
  const s = sizes[size] || sizes.md;
  return /*#__PURE__*/React.createElement("span", _extends({
    style: {
      display: "inline-flex",
      alignItems: "center",
      gap: 5,
      fontFamily: "var(--font-body)",
      fontWeight: 500,
      fontSize: s.fontSize,
      lineHeight: 1.4,
      padding: s.padding,
      borderRadius: "var(--radius-pill)",
      background: p.bg,
      color: p.fg,
      whiteSpace: "nowrap",
      ...style
    }
  }, rest), dot && /*#__PURE__*/React.createElement("span", {
    style: {
      width: 6,
      height: 6,
      borderRadius: "50%",
      background: p.dot,
      flex: "none"
    }
  }), children);
}
Object.assign(__ds_scope, { Badge });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Badge.jsx", error: String((e && e.message) || e) }); }

// components/core/Button.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Button — Tyndall/Tyndall Labs primary control.
 * Variants: primary (clay), secondary (outline), ghost (text), danger.
 */
function Button({
  children,
  variant = "primary",
  size = "md",
  disabled = false,
  iconLeft = null,
  iconRight = null,
  fullWidth = false,
  type = "button",
  onClick,
  style = {},
  ...rest
}) {
  const sizes = {
    sm: {
      fontSize: 13,
      padding: "6px 12px",
      height: 32,
      gap: 6,
      radius: "var(--radius-sm)"
    },
    md: {
      fontSize: 14,
      padding: "9px 16px",
      height: 40,
      gap: 8,
      radius: "var(--radius-md)"
    },
    lg: {
      fontSize: 15,
      padding: "12px 22px",
      height: 48,
      gap: 8,
      radius: "var(--radius-md)"
    }
  };
  const s = sizes[size] || sizes.md;
  const variants = {
    primary: {
      background: "var(--accent)",
      color: "var(--text-on-accent)",
      border: "1px solid transparent"
    },
    secondary: {
      background: "var(--surface-raised)",
      color: "var(--text-primary)",
      border: "1px solid var(--border-strong)"
    },
    ghost: {
      background: "transparent",
      color: "var(--text-primary)",
      border: "1px solid transparent"
    },
    inverse: {
      background: "var(--surface-raised)",
      color: "var(--kraft-950)",
      border: "1px solid transparent"
    },
    danger: {
      background: "var(--status-danger)",
      color: "#fff",
      border: "1px solid transparent"
    }
  };
  const v = variants[variant] || variants.primary;
  const [hover, setHover] = React.useState(false);
  const [active, setActive] = React.useState(false);
  const hoverStyle = hover && !disabled ? variant === "primary" ? {
    background: active ? "var(--accent-active)" : "var(--accent-hover)"
  } : variant === "secondary" ? {
    background: "var(--kraft-50)",
    borderColor: "var(--border-strong)"
  } : variant === "ghost" ? {
    background: "var(--kraft-100)"
  } : variant === "inverse" ? {
    background: "var(--kraft-100)"
  } : {
    background: "var(--clay-700)"
  } : {};
  return /*#__PURE__*/React.createElement("button", _extends({
    type: type,
    disabled: disabled,
    onClick: onClick,
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => {
      setHover(false);
      setActive(false);
    },
    onMouseDown: () => setActive(true),
    onMouseUp: () => setActive(false),
    style: {
      display: fullWidth ? "flex" : "inline-flex",
      width: fullWidth ? "100%" : "auto",
      alignItems: "center",
      justifyContent: "center",
      gap: s.gap,
      fontFamily: "var(--font-body)",
      fontWeight: 500,
      fontSize: s.fontSize,
      lineHeight: 1,
      letterSpacing: "0.005em",
      padding: s.padding,
      minHeight: s.height,
      borderRadius: s.radius,
      cursor: disabled ? "not-allowed" : "pointer",
      opacity: disabled ? 0.45 : 1,
      transition: "background var(--duration-fast) var(--ease-standard), border-color var(--duration-fast) var(--ease-standard)",
      whiteSpace: "nowrap",
      ...v,
      ...hoverStyle,
      ...style
    }
  }, rest), iconLeft && /*#__PURE__*/React.createElement("span", {
    style: {
      display: "inline-flex"
    }
  }, iconLeft), children, iconRight && /*#__PURE__*/React.createElement("span", {
    style: {
      display: "inline-flex"
    }
  }, iconRight));
}
Object.assign(__ds_scope, { Button });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Button.jsx", error: String((e && e.message) || e) }); }

// components/core/Card.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Card — warm raised surface: ivory/white, 1px subtle border, soft shadow.
 * No colored left-border accents.
 */
function Card({
  children,
  padding = "md",
  interactive = false,
  elevation = "sm",
  style = {},
  onClick,
  ...rest
}) {
  const pads = {
    none: 0,
    sm: 16,
    md: 24,
    lg: 32
  };
  const shadows = {
    none: "none",
    sm: "var(--shadow-sm)",
    md: "var(--shadow-md)",
    lg: "var(--shadow-lg)"
  };
  const [hover, setHover] = React.useState(false);
  return /*#__PURE__*/React.createElement("div", _extends({
    onClick: onClick,
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => setHover(false),
    style: {
      background: "var(--surface-raised)",
      border: "1px solid var(--border-subtle)",
      borderRadius: "var(--radius-lg)",
      padding: pads[padding] ?? pads.md,
      boxShadow: interactive && hover ? "var(--shadow-md)" : shadows[elevation],
      borderColor: interactive && hover ? "var(--border-default)" : "var(--border-subtle)",
      transition: "box-shadow var(--duration-normal) var(--ease-standard), border-color var(--duration-normal) var(--ease-standard), transform var(--duration-normal) var(--ease-standard)",
      transform: interactive && hover ? "translateY(-1px)" : "none",
      cursor: interactive ? "pointer" : "default",
      ...style
    }
  }, rest), children);
}
Object.assign(__ds_scope, { Card });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Card.jsx", error: String((e && e.message) || e) }); }

// components/core/Checkbox.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/** Checkbox with brand clay fill and optional label. */
function Checkbox({
  checked,
  onChange,
  label,
  disabled = false,
  id,
  style = {},
  ...rest
}) {
  const autoId = React.useId();
  const cid = id || autoId;
  return /*#__PURE__*/React.createElement("label", {
    htmlFor: cid,
    style: {
      display: "inline-flex",
      alignItems: "center",
      gap: 10,
      fontFamily: "var(--font-sans)",
      fontSize: 14,
      color: "var(--text-primary)",
      cursor: disabled ? "not-allowed" : "pointer",
      opacity: disabled ? 0.5 : 1,
      ...style
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      position: "relative",
      width: 18,
      height: 18,
      flex: "none",
      borderRadius: "var(--radius-xs)",
      border: `1px solid ${checked ? "var(--accent)" : "var(--border-strong)"}`,
      background: checked ? "var(--accent)" : "var(--surface-raised)",
      transition: "background var(--duration-fast) var(--ease-standard), border-color var(--duration-fast) var(--ease-standard)",
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center"
    }
  }, checked && /*#__PURE__*/React.createElement("svg", {
    width: "12",
    height: "12",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "#fff",
    strokeWidth: "3.5",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M20 6 9 17l-5-5"
  })), /*#__PURE__*/React.createElement("input", _extends({
    id: cid,
    type: "checkbox",
    checked: checked,
    disabled: disabled,
    onChange: onChange,
    style: {
      position: "absolute",
      inset: 0,
      opacity: 0,
      margin: 0,
      cursor: "inherit"
    }
  }, rest))), label && /*#__PURE__*/React.createElement("span", null, label));
}
Object.assign(__ds_scope, { Checkbox });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Checkbox.jsx", error: String((e && e.message) || e) }); }

// components/core/Dialog.jsx
try { (() => {
/** Centered modal dialog with warm scrim. Render conditionally on `open`. */
function Dialog({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  width = 460
}) {
  React.useEffect(() => {
    if (!open) return;
    const onKey = e => e.key === "Escape" && onClose && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return /*#__PURE__*/React.createElement("div", {
    onClick: onClose,
    style: {
      position: "fixed",
      inset: 0,
      zIndex: 100,
      background: "var(--surface-overlay)",
      backdropFilter: "blur(2px)",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      padding: 24,
      animation: "dsFade var(--duration-normal) var(--ease-out)"
    }
  }, /*#__PURE__*/React.createElement("div", {
    role: "dialog",
    "aria-modal": "true",
    onClick: e => e.stopPropagation(),
    style: {
      width: "100%",
      maxWidth: width,
      background: "var(--surface-raised)",
      border: "1px solid var(--border-subtle)",
      borderRadius: "var(--radius-xl)",
      boxShadow: "var(--shadow-xl)",
      fontFamily: "var(--font-sans)",
      color: "var(--text-primary)",
      overflow: "hidden",
      animation: "dsRise var(--duration-normal) var(--ease-out)"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "22px 24px 0"
    }
  }, title && /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: "var(--font-serif)",
      fontSize: 22,
      fontWeight: 500,
      letterSpacing: "-0.01em"
    }
  }, title), description && /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 14,
      color: "var(--text-secondary)",
      marginTop: 6,
      lineHeight: 1.5
    }
  }, description)), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "16px 24px"
    }
  }, children), footer && /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      justifyContent: "flex-end",
      gap: 10,
      padding: "14px 24px 20px"
    }
  }, footer)), /*#__PURE__*/React.createElement("style", null, `@keyframes dsFade{from{opacity:0}to{opacity:1}}@keyframes dsRise{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}`));
}
Object.assign(__ds_scope, { Dialog });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Dialog.jsx", error: String((e && e.message) || e) }); }

// components/core/IconButton.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const sizes = {
  sm: 30,
  md: 36,
  lg: 42
};

/**
 * Square icon-only button. Pass a Lucide <i data-lucide> or svg as children.
 */
function IconButton({
  children,
  label,
  variant = "ghost",
  size = "md",
  disabled = false,
  onClick,
  style = {},
  ...rest
}) {
  const [hover, setHover] = React.useState(false);
  const dim = sizes[size] || sizes.md;
  const variants = {
    ghost: {
      background: hover ? "var(--kraft-100)" : "transparent",
      color: "var(--text-secondary)",
      border: "1px solid transparent"
    },
    outline: {
      background: hover ? "var(--kraft-50)" : "var(--surface-raised)",
      color: "var(--text-primary)",
      border: "1px solid var(--border-default)"
    },
    primary: {
      background: hover ? "var(--accent-hover)" : "var(--accent)",
      color: "#fff",
      border: "1px solid transparent"
    }
  };
  return /*#__PURE__*/React.createElement("button", _extends({
    type: "button",
    "aria-label": label,
    title: label,
    disabled: disabled,
    onClick: onClick,
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => setHover(false),
    style: {
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      width: dim,
      height: dim,
      borderRadius: "var(--radius-md)",
      cursor: disabled ? "not-allowed" : "pointer",
      opacity: disabled ? 0.45 : 1,
      transition: "background var(--duration-fast) var(--ease-standard), color var(--duration-fast) var(--ease-standard)",
      ...(variants[variant] || variants.ghost),
      ...style
    }
  }, rest), children);
}
Object.assign(__ds_scope, { IconButton });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/IconButton.jsx", error: String((e && e.message) || e) }); }

// components/core/Input.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Input — single-line text field on a sunken warm well with clay focus ring.
 */
function Input({
  value,
  defaultValue,
  placeholder,
  type = "text",
  size = "md",
  disabled = false,
  invalid = false,
  iconLeft = null,
  onChange,
  style = {},
  ...rest
}) {
  const [focus, setFocus] = React.useState(false);
  const sizes = {
    sm: {
      height: 34,
      fontSize: 13,
      padding: iconLeft ? "0 12px 0 34px" : "0 12px"
    },
    md: {
      height: 40,
      fontSize: 14,
      padding: iconLeft ? "0 14px 0 38px" : "0 14px"
    },
    lg: {
      height: 48,
      fontSize: 15,
      padding: iconLeft ? "0 16px 0 42px" : "0 16px"
    }
  };
  const s = sizes[size] || sizes.md;
  const borderColor = invalid ? "var(--status-danger)" : focus ? "var(--accent)" : "var(--border-default)";
  return /*#__PURE__*/React.createElement("div", {
    style: {
      position: "relative",
      display: "inline-flex",
      alignItems: "center",
      width: "100%",
      ...style
    }
  }, iconLeft && /*#__PURE__*/React.createElement("span", {
    style: {
      position: "absolute",
      left: 12,
      display: "inline-flex",
      color: "var(--text-tertiary)",
      pointerEvents: "none"
    }
  }, iconLeft), /*#__PURE__*/React.createElement("input", _extends({
    type: type,
    value: value,
    defaultValue: defaultValue,
    placeholder: placeholder,
    disabled: disabled,
    onChange: onChange,
    onFocus: () => setFocus(true),
    onBlur: () => setFocus(false),
    style: {
      width: "100%",
      height: s.height,
      fontFamily: "var(--font-body)",
      fontSize: s.fontSize,
      color: "var(--text-primary)",
      padding: s.padding,
      background: disabled ? "var(--kraft-100)" : "var(--surface-sunken)",
      border: `1px solid ${borderColor}`,
      borderRadius: "var(--radius-md)",
      outline: "none",
      boxShadow: focus && !invalid ? "var(--shadow-focus)" : "var(--shadow-inset)",
      opacity: disabled ? 0.6 : 1,
      cursor: disabled ? "not-allowed" : "text",
      transition: "border-color var(--duration-fast) var(--ease-standard), box-shadow var(--duration-fast) var(--ease-standard)"
    }
  }, rest)));
}
Object.assign(__ds_scope, { Input });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Input.jsx", error: String((e && e.message) || e) }); }

// components/core/Radio.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/** Radio button with brand clay dot. */
function Radio({
  checked,
  onChange,
  label,
  name,
  value,
  disabled = false,
  id,
  style = {},
  ...rest
}) {
  const autoId = React.useId();
  const rid = id || autoId;
  return /*#__PURE__*/React.createElement("label", {
    htmlFor: rid,
    style: {
      display: "inline-flex",
      alignItems: "center",
      gap: 10,
      fontFamily: "var(--font-sans)",
      fontSize: 14,
      color: "var(--text-primary)",
      cursor: disabled ? "not-allowed" : "pointer",
      opacity: disabled ? 0.5 : 1,
      ...style
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      position: "relative",
      width: 18,
      height: 18,
      flex: "none",
      borderRadius: "50%",
      border: `1px solid ${checked ? "var(--accent)" : "var(--border-strong)"}`,
      background: "var(--surface-raised)",
      transition: "border-color var(--duration-fast) var(--ease-standard)",
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center"
    }
  }, checked && /*#__PURE__*/React.createElement("span", {
    style: {
      width: 9,
      height: 9,
      borderRadius: "50%",
      background: "var(--accent)"
    }
  }), /*#__PURE__*/React.createElement("input", _extends({
    id: rid,
    type: "radio",
    name: name,
    value: value,
    checked: checked,
    disabled: disabled,
    onChange: onChange,
    style: {
      position: "absolute",
      inset: 0,
      opacity: 0,
      margin: 0,
      cursor: "inherit"
    }
  }, rest))), label && /*#__PURE__*/React.createElement("span", null, label));
}
Object.assign(__ds_scope, { Radio });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Radio.jsx", error: String((e && e.message) || e) }); }

// components/core/Select.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/** Native select styled to match the brand, with a chevron. */
function Select({
  label,
  hint,
  error,
  options = [],
  size = "md",
  disabled = false,
  id,
  style = {},
  ...rest
}) {
  const [focus, setFocus] = React.useState(false);
  const autoId = React.useId();
  const selId = id || autoId;
  const heights = {
    sm: 34,
    md: 40,
    lg: 46
  };
  const h = heights[size] || heights.md;
  const borderColor = error ? "var(--status-danger)" : focus ? "var(--accent)" : "var(--border-default)";
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 6,
      fontFamily: "var(--font-sans)",
      ...style
    }
  }, label && /*#__PURE__*/React.createElement("label", {
    htmlFor: selId,
    style: {
      fontSize: 13,
      fontWeight: 500,
      color: "var(--text-primary)"
    }
  }, label), /*#__PURE__*/React.createElement("div", {
    style: {
      position: "relative",
      display: "flex",
      alignItems: "center"
    }
  }, /*#__PURE__*/React.createElement("select", _extends({
    id: selId,
    disabled: disabled,
    onFocus: () => setFocus(true),
    onBlur: () => setFocus(false),
    style: {
      appearance: "none",
      width: "100%",
      height: h,
      padding: "0 36px 0 12px",
      background: disabled ? "var(--kraft-100)" : "var(--surface-raised)",
      border: `1px solid ${borderColor}`,
      borderRadius: "var(--radius-md)",
      boxShadow: focus ? "var(--shadow-focus)" : "var(--shadow-inset)",
      fontFamily: "var(--font-sans)",
      fontSize: 15,
      color: "var(--text-primary)",
      cursor: disabled ? "not-allowed" : "pointer",
      outline: "none",
      transition: "border-color var(--duration-fast) var(--ease-standard), box-shadow var(--duration-fast) var(--ease-standard)"
    }
  }, rest), options.map(o => {
    const value = typeof o === "string" ? o : o.value;
    const labelText = typeof o === "string" ? o : o.label;
    return /*#__PURE__*/React.createElement("option", {
      key: value,
      value: value
    }, labelText);
  })), /*#__PURE__*/React.createElement("svg", {
    width: "16",
    height: "16",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "var(--text-tertiary)",
    strokeWidth: "2",
    strokeLinecap: "round",
    strokeLinejoin: "round",
    style: {
      position: "absolute",
      right: 12,
      pointerEvents: "none"
    }
  }, /*#__PURE__*/React.createElement("path", {
    d: "m6 9 6 6 6-6"
  }))), (hint || error) && /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 12,
      color: error ? "var(--status-danger)" : "var(--text-tertiary)"
    }
  }, error || hint));
}
Object.assign(__ds_scope, { Select });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Select.jsx", error: String((e && e.message) || e) }); }

// components/core/Switch.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/** Toggle switch with clay "on" state. */
function Switch({
  checked,
  onChange,
  label,
  disabled = false,
  id,
  style = {},
  ...rest
}) {
  const autoId = React.useId();
  const sid = id || autoId;
  return /*#__PURE__*/React.createElement("label", {
    htmlFor: sid,
    style: {
      display: "inline-flex",
      alignItems: "center",
      gap: 10,
      fontFamily: "var(--font-sans)",
      fontSize: 14,
      color: "var(--text-primary)",
      cursor: disabled ? "not-allowed" : "pointer",
      opacity: disabled ? 0.5 : 1,
      ...style
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      position: "relative",
      width: 38,
      height: 22,
      flex: "none",
      borderRadius: "var(--radius-pill)",
      background: checked ? "var(--accent)" : "var(--kraft-300)",
      transition: "background var(--duration-normal) var(--ease-standard)"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      position: "absolute",
      top: 2,
      left: checked ? 18 : 2,
      width: 18,
      height: 18,
      borderRadius: "50%",
      background: "#fff",
      boxShadow: "var(--shadow-sm)",
      transition: "left var(--duration-normal) var(--ease-standard)"
    }
  }), /*#__PURE__*/React.createElement("input", _extends({
    id: sid,
    type: "checkbox",
    role: "switch",
    checked: checked,
    disabled: disabled,
    onChange: onChange,
    style: {
      position: "absolute",
      inset: 0,
      opacity: 0,
      margin: 0,
      cursor: "inherit"
    }
  }, rest))), label && /*#__PURE__*/React.createElement("span", null, label));
}
Object.assign(__ds_scope, { Switch });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Switch.jsx", error: String((e && e.message) || e) }); }

// components/core/Tabs.jsx
try { (() => {
/** Underline tabs. Controlled via `value`/`onChange` or uncontrolled. */
function Tabs({
  tabs = [],
  value,
  defaultValue,
  onChange,
  style = {}
}) {
  const [internal, setInternal] = React.useState(defaultValue ?? tabs[0]?.value);
  const active = value !== undefined ? value : internal;
  const select = v => {
    if (value === undefined) setInternal(v);
    onChange && onChange(v);
  };
  return /*#__PURE__*/React.createElement("div", {
    style: {
      borderBottom: "1px solid var(--border-default)",
      display: "flex",
      gap: 4,
      fontFamily: "var(--font-sans)",
      ...style
    }
  }, tabs.map(t => {
    const isActive = t.value === active;
    return /*#__PURE__*/React.createElement("button", {
      key: t.value,
      type: "button",
      onClick: () => select(t.value),
      style: {
        position: "relative",
        border: "none",
        background: "transparent",
        padding: "10px 12px 12px",
        fontSize: 14,
        fontWeight: isActive ? 600 : 500,
        fontFamily: "var(--font-sans)",
        color: isActive ? "var(--text-primary)" : "var(--text-secondary)",
        cursor: "pointer",
        display: "inline-flex",
        alignItems: "center",
        gap: 7
      }
    }, t.icon, t.label, t.count !== undefined && /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 11,
        fontWeight: 600,
        color: "var(--text-tertiary)",
        background: "var(--kraft-100)",
        borderRadius: "var(--radius-pill)",
        padding: "1px 7px"
      }
    }, t.count), /*#__PURE__*/React.createElement("span", {
      style: {
        position: "absolute",
        left: 8,
        right: 8,
        bottom: -1,
        height: 2,
        borderRadius: 2,
        background: isActive ? "var(--accent)" : "transparent",
        transition: "background var(--duration-fast) var(--ease-standard)"
      }
    }));
  }));
}
Object.assign(__ds_scope, { Tabs });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Tabs.jsx", error: String((e && e.message) || e) }); }

// components/core/Tag.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/** Removable/selectable chip — for filters, attachments, model selection. */
function Tag({
  children,
  selected = false,
  onRemove,
  iconLeft = null,
  onClick,
  style = {},
  ...rest
}) {
  const [hover, setHover] = React.useState(false);
  return /*#__PURE__*/React.createElement("span", _extends({
    onClick: onClick,
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => setHover(false),
    style: {
      display: "inline-flex",
      alignItems: "center",
      gap: 6,
      height: 28,
      padding: onRemove ? "0 6px 0 10px" : "0 12px",
      fontFamily: "var(--font-sans)",
      fontSize: 13,
      fontWeight: 500,
      borderRadius: "var(--radius-pill)",
      cursor: onClick ? "pointer" : "default",
      background: selected ? "var(--clay-50)" : hover && onClick ? "var(--kraft-100)" : "var(--surface-raised)",
      color: selected ? "var(--clay-700)" : "var(--text-primary)",
      border: `1px solid ${selected ? "var(--clay-200)" : "var(--border-default)"}`,
      transition: "background var(--duration-fast) var(--ease-standard), border-color var(--duration-fast) var(--ease-standard)",
      whiteSpace: "nowrap",
      ...style
    }
  }, rest), iconLeft && /*#__PURE__*/React.createElement("span", {
    style: {
      display: "inline-flex",
      color: "var(--text-tertiary)"
    }
  }, iconLeft), children, onRemove && /*#__PURE__*/React.createElement("button", {
    type: "button",
    "aria-label": "Remove",
    onClick: e => {
      e.stopPropagation();
      onRemove(e);
    },
    style: {
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      width: 18,
      height: 18,
      border: "none",
      borderRadius: "50%",
      background: "transparent",
      color: "var(--text-tertiary)",
      cursor: "pointer"
    }
  }, /*#__PURE__*/React.createElement("svg", {
    width: "12",
    height: "12",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2.5",
    strokeLinecap: "round"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M18 6 6 18M6 6l12 12"
  }))));
}
Object.assign(__ds_scope, { Tag });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Tag.jsx", error: String((e && e.message) || e) }); }

// components/core/Textarea.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/** Multi-line text input, matched to Input styling. */
function Textarea({
  label,
  hint,
  error,
  rows = 4,
  disabled = false,
  id,
  style = {},
  ...rest
}) {
  const [focus, setFocus] = React.useState(false);
  const autoId = React.useId();
  const inputId = id || autoId;
  const borderColor = error ? "var(--status-danger)" : focus ? "var(--accent)" : "var(--border-default)";
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 6,
      fontFamily: "var(--font-sans)",
      ...style
    }
  }, label && /*#__PURE__*/React.createElement("label", {
    htmlFor: inputId,
    style: {
      fontSize: 13,
      fontWeight: 500,
      color: "var(--text-primary)"
    }
  }, label), /*#__PURE__*/React.createElement("textarea", _extends({
    id: inputId,
    rows: rows,
    disabled: disabled,
    onFocus: () => setFocus(true),
    onBlur: () => setFocus(false),
    style: {
      resize: "vertical",
      padding: "10px 12px",
      background: disabled ? "var(--kraft-100)" : "var(--surface-raised)",
      border: `1px solid ${borderColor}`,
      borderRadius: "var(--radius-md)",
      boxShadow: focus ? "var(--shadow-focus)" : "var(--shadow-inset)",
      fontFamily: "var(--font-sans)",
      fontSize: 15,
      lineHeight: 1.5,
      color: "var(--text-primary)",
      outline: "none",
      transition: "border-color var(--duration-fast) var(--ease-standard), box-shadow var(--duration-fast) var(--ease-standard)"
    }
  }, rest)), (hint || error) && /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 12,
      color: error ? "var(--status-danger)" : "var(--text-tertiary)"
    }
  }, error || hint));
}
Object.assign(__ds_scope, { Textarea });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Textarea.jsx", error: String((e && e.message) || e) }); }

// components/core/Tooltip.jsx
try { (() => {
/** Hover/focus tooltip. Wraps a single child trigger. */
function Tooltip({
  content,
  side = "top",
  children,
  style = {}
}) {
  const [open, setOpen] = React.useState(false);
  const pos = {
    top: {
      bottom: "calc(100% + 8px)",
      left: "50%",
      transform: "translateX(-50%)"
    },
    bottom: {
      top: "calc(100% + 8px)",
      left: "50%",
      transform: "translateX(-50%)"
    },
    left: {
      right: "calc(100% + 8px)",
      top: "50%",
      transform: "translateY(-50%)"
    },
    right: {
      left: "calc(100% + 8px)",
      top: "50%",
      transform: "translateY(-50%)"
    }
  };
  return /*#__PURE__*/React.createElement("span", {
    style: {
      position: "relative",
      display: "inline-flex",
      ...style
    },
    onMouseEnter: () => setOpen(true),
    onMouseLeave: () => setOpen(false),
    onFocus: () => setOpen(true),
    onBlur: () => setOpen(false)
  }, children, open && /*#__PURE__*/React.createElement("span", {
    role: "tooltip",
    style: {
      position: "absolute",
      ...pos[side],
      zIndex: 50,
      background: "var(--kraft-950)",
      color: "var(--kraft-25)",
      fontFamily: "var(--font-sans)",
      fontSize: 12,
      fontWeight: 500,
      lineHeight: 1.4,
      padding: "6px 9px",
      borderRadius: "var(--radius-sm)",
      boxShadow: "var(--shadow-md)",
      whiteSpace: "nowrap",
      pointerEvents: "none"
    }
  }, content));
}
Object.assign(__ds_scope, { Tooltip });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Tooltip.jsx", error: String((e && e.message) || e) }); }

// ui_kits/markets/app.jsx
try { (() => {
// Tyndall Markets — dashboard view, AI analysis panel, orchestrator
const M = window.ClaudeDesignSystem_9a1625;
const {
  Ico,
  Chart,
  Sidebar,
  TopBar,
  TICKERS,
  WATCH,
  PRICE,
  TFS
} = window;
function Stat({
  k,
  v
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "12px 14px",
      border: "1px solid var(--border-subtle)",
      borderRadius: "var(--radius-md)",
      background: "var(--surface-raised)"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11.5,
      color: "var(--text-tertiary)",
      marginBottom: 4
    }
  }, k), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 15.5,
      fontWeight: 600,
      fontFamily: "var(--font-sans)",
      color: "var(--text-primary)"
    }
  }, v));
}
function AIAnalysis({
  t,
  sym,
  thread,
  onAsk,
  draft,
  setDraft
}) {
  const ratingTone = t.rating === "Bullish" ? "success" : t.rating === "Neutral" ? "neutral" : t.rating === "Volatile" ? "warning" : "accent";
  return /*#__PURE__*/React.createElement(M.Card, {
    padding: "none",
    style: {
      overflow: "hidden"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 11,
      padding: "16px 20px",
      borderBottom: "1px solid var(--border-subtle)"
    }
  }, /*#__PURE__*/React.createElement(M.Avatar, {
    brand: true,
    size: "sm"
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 14.5,
      fontWeight: 600
    }
  }, "AI analyst"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 12,
      color: "var(--text-tertiary)"
    }
  }, "Tyndall Lumen \xB7 ", sym, " read")), /*#__PURE__*/React.createElement(M.Badge, {
    tone: ratingTone
  }, t.rating)), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "18px 20px"
    }
  }, /*#__PURE__*/React.createElement("p", {
    style: {
      margin: 0,
      fontFamily: "var(--font-prose)",
      fontSize: 15.5,
      lineHeight: 1.62,
      color: "var(--text-primary)"
    }
  }, t.summary), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "1fr 1fr",
      gap: 16,
      marginTop: 18
    }
  }, [["Bull case", t.bull, "var(--status-success)", "trending-up"], ["Bear case", t.bear, "var(--status-danger)", "trending-down"]].map(([label, items, color, ic]) => /*#__PURE__*/React.createElement("div", {
    key: label
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 6,
      fontSize: 12,
      fontWeight: 700,
      letterSpacing: "0.04em",
      textTransform: "uppercase",
      color,
      marginBottom: 9
    }
  }, /*#__PURE__*/React.createElement(Ico, {
    n: ic,
    s: 15
  }), " ", label), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 8
    }
  }, items.map((x, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    style: {
      display: "flex",
      gap: 8,
      fontSize: 13.5,
      lineHeight: 1.45,
      color: "var(--text-secondary)"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color,
      flex: "none",
      marginTop: 1
    }
  }, "\u2022"), x)))))), thread.length > 0 && /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 18,
      display: "flex",
      flexDirection: "column",
      gap: 14,
      borderTop: "1px solid var(--border-subtle)",
      paddingTop: 16
    }
  }, thread.map((m, i) => /*#__PURE__*/React.createElement("div", {
    key: i
  }, m.role === "user" ? /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      justifyContent: "flex-end"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      background: "var(--surface-sunken)",
      border: "1px solid var(--border-subtle)",
      borderRadius: "var(--radius-lg)",
      padding: "9px 13px",
      fontSize: 13.5,
      maxWidth: 460
    }
  }, m.text)) : /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 10
    }
  }, /*#__PURE__*/React.createElement(M.Avatar, {
    brand: true,
    size: "sm"
  }), /*#__PURE__*/React.createElement("p", {
    style: {
      margin: 0,
      fontFamily: "var(--font-prose)",
      fontSize: 14.5,
      lineHeight: 1.6,
      color: "var(--text-primary)",
      maxWidth: 520
    }
  }, m.text)))))), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "0 20px 18px"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 8,
      alignItems: "center",
      background: "var(--surface-sunken)",
      border: "1px solid var(--border-default)",
      borderRadius: "var(--radius-pill)",
      padding: "5px 6px 5px 16px"
    }
  }, /*#__PURE__*/React.createElement(Ico, {
    n: "sparkles",
    s: 16
  }), /*#__PURE__*/React.createElement("input", {
    value: draft,
    onChange: e => setDraft(e.target.value),
    onKeyDown: e => {
      if (e.key === "Enter") onAsk();
    },
    placeholder: `Ask about ${sym} — valuation, risks, peers…`,
    style: {
      flex: 1,
      border: "none",
      outline: "none",
      background: "transparent",
      fontFamily: "var(--font-sans)",
      fontSize: 14,
      color: "var(--text-primary)"
    }
  }), /*#__PURE__*/React.createElement(IconButton, {
    label: "Ask",
    variant: "primary",
    onClick: onAsk
  }, /*#__PURE__*/React.createElement(Ico, {
    n: "arrow-up"
  })))));
}
function Dashboard({
  sym,
  setSym
}) {
  const t = TICKERS[sym];
  const up = t.chg >= 0;
  const col = up ? "var(--status-success)" : "var(--status-danger)";
  const [tf, setTf] = React.useState("1M");
  const [thread, setThread] = React.useState([]);
  const [draft, setDraft] = React.useState("");
  React.useEffect(() => {
    setThread([]);
  }, [sym]);
  const ask = () => {
    const q = draft.trim();
    if (!q) return;
    setThread(x => [...x, {
      role: "user",
      text: q
    }]);
    setDraft("");
    setTimeout(() => setThread(x => [...x, {
      role: "assistant",
      text: `On ${sym}: the short answer is it depends on your time horizon. Over the next year the setup is ${t.rating.toLowerCase()} — ${t.bull[0].toLowerCase()}, balanced against ${t.bear[0].toLowerCase()}. I'd size the position to that uncertainty rather than the headline.`
    }]), 500);
  };
  return /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      overflow: "auto",
      padding: "24px 28px 40px",
      background: "var(--surface-canvas)"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "minmax(0,1fr) 300px",
      gap: 24,
      maxWidth: 1180,
      margin: "0 auto"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 20
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "flex-end",
      gap: 16
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 10
    }
  }, /*#__PURE__*/React.createElement("h1", {
    style: {
      margin: 0,
      fontFamily: "var(--font-serif)",
      fontSize: 34,
      fontWeight: 500,
      letterSpacing: "-0.02em"
    }
  }, sym), /*#__PURE__*/React.createElement(M.Tag, null, t.sector)), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 14,
      color: "var(--text-secondary)",
      marginTop: 2
    }
  }, t.name)), /*#__PURE__*/React.createElement("div", {
    style: {
      marginLeft: "auto",
      textAlign: "right"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 30,
      fontWeight: 600,
      fontFamily: "var(--font-sans)",
      letterSpacing: "-0.01em"
    }
  }, "$", t.price.toLocaleString()), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 14.5,
      fontWeight: 600,
      color: col,
      display: "flex",
      alignItems: "center",
      gap: 4,
      justifyContent: "flex-end"
    }
  }, /*#__PURE__*/React.createElement(Ico, {
    n: up ? "arrow-up-right" : "arrow-down-right",
    s: 16
  }), up ? "+" : "", t.chg, "% today"))), /*#__PURE__*/React.createElement(M.Card, {
    padding: "none",
    style: {
      overflow: "hidden"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 6,
      padding: "12px 16px",
      borderBottom: "1px solid var(--border-subtle)"
    }
  }, TFS.map(x => /*#__PURE__*/React.createElement("button", {
    key: x,
    onClick: () => setTf(x),
    style: {
      border: "none",
      cursor: "pointer",
      padding: "5px 12px",
      borderRadius: "var(--radius-pill)",
      fontFamily: "var(--font-sans)",
      fontSize: 12.5,
      fontWeight: 600,
      color: tf === x ? "var(--text-on-accent)" : "var(--text-secondary)",
      background: tf === x ? "var(--accent)" : "transparent"
    }
  }, x))), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "10px 8px 4px"
    }
  }, /*#__PURE__*/React.createElement(Chart, {
    seed: t.seed + tf.length * 11,
    drift: t.drift,
    up: up
  }))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "repeat(3,1fr)",
      gap: 10
    }
  }, Object.entries(t.stats).map(([k, v]) => /*#__PURE__*/React.createElement(Stat, {
    key: k,
    k: k,
    v: v
  }))), /*#__PURE__*/React.createElement(AIAnalysis, {
    t: t,
    sym: sym,
    thread: thread,
    onAsk: ask,
    draft: draft,
    setDraft: setDraft
  })), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 12,
      fontWeight: 700,
      letterSpacing: "0.05em",
      textTransform: "uppercase",
      color: "var(--text-tertiary)",
      margin: "4px 4px 10px"
    }
  }, "Watchlist"), /*#__PURE__*/React.createElement(M.Card, {
    padding: "none",
    style: {
      overflow: "hidden"
    }
  }, WATCH.map((w, i) => {
    const wu = w.chg >= 0,
      active = w.sym === sym;
    return /*#__PURE__*/React.createElement("button", {
      key: w.sym,
      onClick: () => TICKERS[w.sym] && setSym(w.sym),
      style: {
        width: "100%",
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "12px 15px",
        border: "none",
        borderTop: i ? "1px solid var(--border-subtle)" : "none",
        cursor: TICKERS[w.sym] ? "pointer" : "default",
        background: active ? "var(--accent-subtle)" : "transparent",
        textAlign: "left"
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        flex: 1
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 13.5,
        fontWeight: 600
      }
    }, w.sym), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 12,
        color: "var(--text-tertiary)"
      }
    }, "$", PRICE[w.sym].toLocaleString())), /*#__PURE__*/React.createElement("div", {
      style: {
        fontSize: 13,
        fontWeight: 600,
        color: wu ? "var(--status-success)" : "var(--status-danger)"
      }
    }, wu ? "+" : "", w.chg, "%"));
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 14
    }
  }, /*#__PURE__*/React.createElement(M.Card, {
    style: {
      background: "var(--surface-inverse)",
      border: "none"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 8,
      color: "var(--kraft-25)",
      fontSize: 13.5,
      fontWeight: 600,
      marginBottom: 8
    }
  }, /*#__PURE__*/React.createElement(Ico, {
    n: "sparkles",
    s: 16
  }), " Daily brief"), /*#__PURE__*/React.createElement("p", {
    style: {
      margin: 0,
      fontFamily: "var(--font-prose)",
      fontSize: 13.5,
      lineHeight: 1.55,
      color: "var(--kraft-300)"
    }
  }, "Semis led the tape today on data-center demand. Rates drifted lower; megacaps mixed. Your watchlist is up 0.9% on average."))))));
}
function App() {
  const [sym, setSym] = React.useState("NVDA");
  const [query, setQuery] = React.useState("");
  React.useEffect(() => {
    setTimeout(() => window.lucide && window.lucide.createIcons(), 30);
  });
  const search = () => {
    const q = query.trim().toUpperCase();
    if (TICKERS[q]) {
      setSym(q);
      setQuery("");
    }
  };
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      height: "100%",
      background: "var(--surface-canvas)"
    }
  }, /*#__PURE__*/React.createElement(Sidebar, null), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      display: "flex",
      flexDirection: "column",
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement(TopBar, {
    query: query,
    setQuery: setQuery,
    onSearch: search
  }), /*#__PURE__*/React.createElement(Dashboard, {
    sym: sym,
    setSym: setSym
  })));
}
Object.assign(window, {
  App
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/markets/app.jsx", error: String((e && e.message) || e) }); }

// ui_kits/markets/chrome.jsx
try { (() => {
// Tyndall Markets — AI equity-analysis platform (Claude-style)
const {
  Button,
  IconButton,
  Input,
  Badge,
  Card,
  Avatar,
  Tag
} = window.ClaudeDesignSystem_9a1625;
const Ico = ({
  n,
  s = 18
}) => /*#__PURE__*/React.createElement("i", {
  "data-lucide": n,
  style: {
    width: s,
    height: s
  }
});

// ---- seeded data ---------------------------------------------------------
function mulberry32(a) {
  return function () {
    a |= 0;
    a = a + 0x6D2B79F5 | 0;
    let t = Math.imul(a ^ a >>> 15, 1 | a);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}
function series(seed, n, drift) {
  const r = mulberry32(seed);
  const out = [];
  let v = 100;
  for (let i = 0; i < n; i++) {
    v += (r() - 0.5) * 6 + drift;
    out.push(v);
  }
  const min = Math.min(...out),
    max = Math.max(...out);
  return out.map(x => (x - min) / (max - min || 1));
}
const TICKERS = {
  NVDA: {
    name: "NVIDIA Corporation",
    sector: "Semiconductors",
    price: 1284.32,
    chg: 2.41,
    seed: 7,
    drift: 0.55,
    stats: {
      "Market cap": "$3.16T",
      "P/E ratio": "68.4",
      "Volume": "41.2M",
      "52-wk range": "$394–$1,312",
      "Div yield": "0.02%",
      "Beta": "1.74"
    },
    rating: "Bullish",
    summary: "NVIDIA's data-center momentum remains the dominant story. Blackwell demand is outrunning supply into 2027, and the moat around CUDA keeps switching costs high. The risk is concentration — a handful of hyperscalers drive most revenue — and a valuation that already prices in flawless execution.",
    bull: ["Data-center revenue up triple digits year over year", "Blackwell backlog extends visibility into 2027", "Software + networking deepen the platform lock-in"],
    bear: ["~40% of revenue from a few hyperscale buyers", "Custom silicon (TPU, Trainium) chips at the edges", "Multiple leaves little room for a demand air-pocket"]
  },
  AAPL: {
    name: "Apple Inc.",
    sector: "Consumer Electronics",
    price: 232.18,
    chg: -0.62,
    seed: 19,
    drift: 0.12,
    stats: {
      "Market cap": "$3.52T",
      "P/E ratio": "35.1",
      "Volume": "52.8M",
      "52-wk range": "$164–$237",
      "Div yield": "0.43%",
      "Beta": "1.21"
    },
    rating: "Neutral",
    summary: "Apple is a cash-compounding machine with a services flywheel that keeps gross margin climbing. Near-term, iPhone units are flattish and the AI roadmap is still proving itself. The stock rarely gets cheap; you're paying for durability, not growth.",
    bull: ["Services at record gross margin and still growing", "Installed base over 2.2B active devices", "Buybacks shrink the share count every quarter"],
    bear: ["iPhone unit growth has stalled in key markets", "On-device AI features lag the frontier", "Regulatory pressure on App Store economics"]
  },
  TSLA: {
    name: "Tesla, Inc.",
    sector: "Automobiles",
    price: 408.77,
    chg: 4.18,
    seed: 31,
    drift: 0.34,
    stats: {
      "Market cap": "$1.31T",
      "P/E ratio": "112",
      "Volume": "98.4M",
      "52-wk range": "$138–$415",
      "Div yield": "—",
      "Beta": "2.31"
    },
    rating: "Volatile",
    summary: "Tesla trades as an autonomy and energy option more than a carmaker. Auto margins are compressing under price cuts, while the bull case rests on robotaxi and storage scaling on schedule — outcomes that are real but hard to underwrite. Expect wide swings.",
    bull: ["Energy storage deployments inflecting sharply", "FSD and robotaxi optionality not in base numbers", "Cost-per-vehicle still trending down"],
    bear: ["Automotive gross margin under price-war pressure", "Robotaxi timeline has slipped before", "Valuation depends on non-auto bets landing"]
  }
};
const WATCH = [{
  sym: "NVDA",
  chg: 2.41
}, {
  sym: "AAPL",
  chg: -0.62
}, {
  sym: "TSLA",
  chg: 4.18
}, {
  sym: "MSFT",
  chg: 0.88
}, {
  sym: "AMD",
  chg: -1.34
}, {
  sym: "GOOGL",
  chg: 1.07
}];
const PRICE = {
  NVDA: 1284.32,
  AAPL: 232.18,
  TSLA: 408.77,
  MSFT: 478.9,
  AMD: 162.44,
  GOOGL: 191.6
};
const TFS = ["1D", "1W", "1M", "6M", "1Y", "5Y"];

// ---- chart ---------------------------------------------------------------
function Chart({
  seed,
  drift,
  up
}) {
  const W = 720,
    H = 240,
    P = 8;
  const pts = React.useMemo(() => series(seed, 56, drift), [seed, drift]);
  const stroke = up ? "var(--status-success)" : "var(--status-danger)";
  const x = i => P + i / (pts.length - 1) * (W - P * 2);
  const y = v => H - P - v * (H - P * 2);
  const line = pts.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(" ");
  const area = `${line} L${x(pts.length - 1)} ${H} L${x(0)} ${H} Z`;
  const gid = "g" + seed;
  return /*#__PURE__*/React.createElement("svg", {
    viewBox: `0 0 ${W} ${H}`,
    style: {
      width: "100%",
      height: 240,
      display: "block"
    },
    preserveAspectRatio: "none"
  }, /*#__PURE__*/React.createElement("defs", null, /*#__PURE__*/React.createElement("linearGradient", {
    id: gid,
    x1: "0",
    y1: "0",
    x2: "0",
    y2: "1"
  }, /*#__PURE__*/React.createElement("stop", {
    offset: "0%",
    stopColor: stroke,
    stopOpacity: "0.16"
  }), /*#__PURE__*/React.createElement("stop", {
    offset: "100%",
    stopColor: stroke,
    stopOpacity: "0"
  }))), [0.25, 0.5, 0.75].map(g => /*#__PURE__*/React.createElement("line", {
    key: g,
    x1: "0",
    x2: W,
    y1: H * g,
    y2: H * g,
    stroke: "var(--border-subtle)",
    strokeWidth: "1"
  })), /*#__PURE__*/React.createElement("path", {
    d: area,
    fill: `url(#${gid})`
  }), /*#__PURE__*/React.createElement("path", {
    d: line,
    fill: "none",
    stroke: stroke,
    strokeWidth: "2",
    strokeLinejoin: "round",
    strokeLinecap: "round"
  }));
}

// ---- sidebar + topbar ----------------------------------------------------
const NAV = [["layout-dashboard", "Dashboard", true], ["star", "Watchlist", false], ["filter", "Screener", false], ["sparkles", "AI analyst", false], ["briefcase", "Portfolio", false], ["bell", "Alerts", false]];
function Sidebar() {
  return /*#__PURE__*/React.createElement("aside", {
    style: {
      width: 232,
      flex: "none",
      height: "100%",
      boxSizing: "border-box",
      background: "var(--surface-panel)",
      borderRight: "1px solid var(--border-subtle)",
      display: "flex",
      flexDirection: "column",
      padding: "16px 12px"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 9,
      padding: "4px 8px 18px"
    }
  }, /*#__PURE__*/React.createElement("img", {
    src: "../../assets/brand-mark.svg",
    style: {
      width: 24
    },
    alt: ""
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: "var(--font-serif)",
      fontSize: 19,
      fontWeight: 500,
      letterSpacing: "-0.01em"
    }
  }, "Markets")), /*#__PURE__*/React.createElement("nav", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 2
    }
  }, NAV.map(([ic, label, active]) => /*#__PURE__*/React.createElement("div", {
    key: label,
    style: {
      display: "flex",
      alignItems: "center",
      gap: 10,
      padding: "9px 12px",
      borderRadius: "var(--radius-md)",
      cursor: "pointer",
      fontSize: 14,
      fontWeight: active ? 600 : 500,
      color: active ? "var(--text-primary)" : "var(--text-secondary)",
      background: active ? "var(--surface-raised)" : "transparent",
      boxShadow: active ? "var(--shadow-xs)" : "none"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: active ? "var(--accent)" : "var(--text-tertiary)",
      display: "inline-flex"
    }
  }, /*#__PURE__*/React.createElement(Ico, {
    n: ic,
    s: 17
  })), label))), /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: "auto",
      borderTop: "1px solid var(--border-subtle)",
      paddingTop: 12,
      display: "flex",
      alignItems: "center",
      gap: 10
    }
  }, /*#__PURE__*/React.createElement(Avatar, {
    name: "Ada Lovelace",
    size: "sm"
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      lineHeight: 1.2
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 13,
      fontWeight: 600
    }
  }, "Ada Lovelace"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11.5,
      color: "var(--text-tertiary)"
    }
  }, "Pro plan"))));
}
function TopBar({
  query,
  setQuery,
  onSearch
}) {
  return /*#__PURE__*/React.createElement("header", {
    style: {
      height: 60,
      flex: "none",
      display: "flex",
      alignItems: "center",
      gap: 14,
      padding: "0 22px",
      borderBottom: "1px solid var(--border-subtle)",
      background: "var(--surface-canvas)"
    }
  }, /*#__PURE__*/React.createElement("form", {
    onSubmit: e => {
      e.preventDefault();
      onSearch();
    },
    style: {
      width: 320
    }
  }, /*#__PURE__*/React.createElement(Input, {
    value: query,
    onChange: e => setQuery(e.target.value),
    placeholder: "Search a ticker \u2014 try AAPL, TSLA",
    iconLeft: /*#__PURE__*/React.createElement(Ico, {
      n: "search",
      s: 16
    })
  })), /*#__PURE__*/React.createElement(Badge, {
    tone: "success",
    dot: true
  }, "Markets open"), /*#__PURE__*/React.createElement("div", {
    style: {
      marginLeft: "auto",
      display: "flex",
      alignItems: "center",
      gap: 6
    }
  }, /*#__PURE__*/React.createElement(IconButton, {
    label: "Notifications"
  }, /*#__PURE__*/React.createElement(Ico, {
    n: "bell"
  })), /*#__PURE__*/React.createElement(IconButton, {
    label: "Settings"
  }, /*#__PURE__*/React.createElement(Ico, {
    n: "settings"
  }))));
}
Object.assign(window, {
  Ico,
  Chart,
  Sidebar,
  TopBar,
  TICKERS,
  WATCH,
  PRICE,
  TFS
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/markets/chrome.jsx", error: String((e && e.message) || e) }); }

// ui_kits/worldforge/app.jsx
try { (() => {
// Tyndall Worldforge — 2D → interactive 3D world builder (Claude-style)
const W = window.ClaudeDesignSystem_9a1625;
const Icon = ({
  n,
  s = 18
}) => /*#__PURE__*/React.createElement("i", {
  "data-lucide": n,
  style: {
    width: s,
    height: s
  }
});
const LAYERS = [{
  name: "Sky",
  color: "linear-gradient(180deg,#cdd8e6,#e7ddcf)",
  z: 10
}, {
  name: "Hills",
  color: "linear-gradient(180deg,#9fae8f,#7d8a6c)",
  z: 70
}, {
  name: "Buildings",
  color: "linear-gradient(180deg,#d6a98c,#b66f4c)",
  z: 140
}, {
  name: "Subject",
  color: "linear-gradient(180deg,#e8b59a,#cc785c)",
  z: 220
}];

// ---------- 3D viewport ----------
function Viewport({
  generated,
  spin,
  physics
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      position: "relative",
      flex: 1,
      minHeight: 0,
      overflow: "hidden",
      background: "radial-gradient(120% 90% at 50% 18%, #232220 0%, #131312 70%)"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      position: "absolute",
      top: 14,
      left: 16,
      zIndex: 5,
      display: "flex",
      gap: 8,
      alignItems: "center"
    }
  }, /*#__PURE__*/React.createElement(W.Badge, {
    tone: generated ? "success" : "warning",
    dot: true
  }, generated ? "World ready" : "Awaiting build"), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 12,
      color: "rgba(255,255,255,0.5)",
      fontFamily: "var(--font-mono)"
    }
  }, "depth \xB7 4 layers")), /*#__PURE__*/React.createElement("div", {
    style: {
      position: "absolute",
      inset: 0,
      perspective: "1200px",
      perspectiveOrigin: "50% 36%"
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "wf-scene" + (spin ? " wf-spin" : ""),
    style: {
      position: "absolute",
      left: "50%",
      top: "54%",
      width: 0,
      height: 0,
      transformStyle: "preserve-3d",
      transform: "translate(-50%,-50%) rotateX(60deg) rotateZ(-24deg)"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      position: "absolute",
      width: 520,
      height: 520,
      left: -260,
      top: -260,
      background: "repeating-linear-gradient(0deg, rgba(217,119,87,0.16) 0 1px, transparent 1px 40px), repeating-linear-gradient(90deg, rgba(217,119,87,0.16) 0 1px, transparent 1px 40px)",
      borderRadius: 8,
      boxShadow: "0 0 0 1px rgba(217,119,87,0.18)",
      maskImage: "radial-gradient(circle at 50% 50%, #000 55%, transparent 78%)",
      WebkitMaskImage: "radial-gradient(circle at 50% 50%, #000 55%, transparent 78%)"
    }
  }), LAYERS.map((l, i) => {
    const size = 260 - i * 44;
    const off = (i - 1.5) * 26;
    return /*#__PURE__*/React.createElement("div", {
      key: l.name,
      className: "wf-slice",
      style: {
        position: "absolute",
        width: size,
        height: size,
        left: -size / 2 + off,
        top: -size / 2 + off,
        background: l.color,
        borderRadius: 16,
        border: "1px solid rgba(255,255,255,0.35)",
        boxShadow: "0 12px 26px rgba(0,0,0,0.4)",
        transform: `translateZ(${generated ? l.z : 4}px)`,
        opacity: generated ? 1 : i === 3 ? 1 : 0.12,
        transition: `transform .7s cubic-bezier(.16,1,.3,1) ${i * 70}ms, opacity .5s ease ${i * 70}ms`
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        position: "absolute",
        left: 12,
        top: 9,
        fontSize: 12,
        fontWeight: 600,
        color: "rgba(20,20,19,0.62)",
        fontFamily: "var(--font-sans)"
      }
    }, l.name));
  }), physics && [0, 1, 2].map(i => /*#__PURE__*/React.createElement("div", {
    key: i,
    className: "wf-drop",
    style: {
      position: "absolute",
      width: 26,
      height: 26,
      left: -13 + (i - 1) * 70,
      top: -13 + 60,
      background: ["#D97757", "#5A7052", "#4F6B8F"][i],
      borderRadius: 6,
      boxShadow: "0 8px 16px rgba(0,0,0,0.45)",
      transform: "translateZ(260px)",
      animation: `wf-fall .9s cubic-bezier(.5,0,.6,1) ${i * 120}ms both`
    }
  })))), /*#__PURE__*/React.createElement("div", {
    style: {
      position: "absolute",
      bottom: 16,
      left: "50%",
      transform: "translateX(-50%)",
      zIndex: 5,
      display: "flex",
      gap: 6,
      background: "rgba(20,20,19,0.6)",
      backdropFilter: "blur(8px)",
      padding: 6,
      borderRadius: "var(--radius-pill)",
      border: "1px solid rgba(255,255,255,0.1)"
    }
  }, [["move-3d", "Orbit"], ["maximize", "Frame"], ["scan", "Depth"], ["box", "Mesh"]].map(([ic, lbl]) => /*#__PURE__*/React.createElement("button", {
    key: lbl,
    style: {
      display: "inline-flex",
      alignItems: "center",
      gap: 6,
      border: "none",
      background: "transparent",
      color: "rgba(255,255,255,0.78)",
      fontFamily: "var(--font-sans)",
      fontSize: 12.5,
      fontWeight: 500,
      padding: "6px 12px",
      borderRadius: "var(--radius-pill)",
      cursor: "pointer"
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    n: ic,
    s: 15
  }), " ", lbl))));
}

// ---------- right control panel ----------
function Field({
  label,
  children
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      marginBottom: 18
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 12,
      fontWeight: 600,
      color: "var(--text-secondary)",
      marginBottom: 8
    }
  }, label), children);
}
function Slider({
  value,
  onChange
}) {
  return /*#__PURE__*/React.createElement("input", {
    type: "range",
    min: "0",
    max: "100",
    value: value,
    onChange: e => onChange(+e.target.value),
    style: {
      width: "100%",
      accentColor: "var(--accent)"
    }
  });
}
function Controls({
  depth,
  setDepth,
  physics,
  setPhysics,
  collide,
  setCollide
}) {
  return /*#__PURE__*/React.createElement("aside", {
    style: {
      width: 280,
      flex: "none",
      borderLeft: "1px solid var(--border-subtle)",
      background: "var(--surface-panel)",
      padding: "20px 18px",
      overflow: "auto"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: "var(--font-serif)",
      fontSize: 18,
      fontWeight: 500,
      marginBottom: 18
    }
  }, "Scene"), /*#__PURE__*/React.createElement(Field, {
    label: `Depth strength · ${depth}%`
  }, /*#__PURE__*/React.createElement(Slider, {
    value: depth,
    onChange: setDepth
  })), /*#__PURE__*/React.createElement(Field, {
    label: "Detected layers"
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 4
    }
  }, LAYERS.map(l => /*#__PURE__*/React.createElement("div", {
    key: l.name,
    style: {
      display: "flex",
      alignItems: "center",
      gap: 10,
      padding: "8px 10px",
      background: "var(--surface-raised)",
      border: "1px solid var(--border-subtle)",
      borderRadius: "var(--radius-sm)"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 14,
      height: 14,
      borderRadius: 4,
      background: l.color,
      flex: "none",
      border: "1px solid rgba(0,0,0,0.1)"
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 13,
      flex: 1
    }
  }, l.name), /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--text-tertiary)"
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    n: "eye",
    s: 15
  })))))), /*#__PURE__*/React.createElement(Field, {
    label: "Physics"
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 10,
      padding: "12px 12px",
      background: "var(--surface-raised)",
      border: "1px solid var(--border-subtle)",
      borderRadius: "var(--radius-md)"
    }
  }, /*#__PURE__*/React.createElement("label", {
    style: {
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      fontSize: 13.5
    }
  }, "Gravity ", /*#__PURE__*/React.createElement(W.Switch, {
    checked: physics,
    onChange: e => setPhysics(e.target.checked)
  })), /*#__PURE__*/React.createElement("label", {
    style: {
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      fontSize: 13.5
    }
  }, "Collisions ", /*#__PURE__*/React.createElement(W.Switch, {
    checked: collide,
    onChange: e => setCollide(e.target.checked)
  })))), /*#__PURE__*/React.createElement(Field, {
    label: "Export"
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 8
    }
  }, /*#__PURE__*/React.createElement(W.Button, {
    variant: "secondary",
    size: "sm",
    iconLeft: /*#__PURE__*/React.createElement(Icon, {
      n: "box",
      s: 15
    })
  }, "GLB"), /*#__PURE__*/React.createElement(W.Button, {
    variant: "secondary",
    size: "sm",
    iconLeft: /*#__PURE__*/React.createElement(Icon, {
      n: "globe",
      s: 15
    })
  }, "USDZ"))));
}

// ---------- left source panel ----------
function SourcePanel({
  onGenerate,
  busy,
  generated,
  prompt,
  setPrompt
}) {
  return /*#__PURE__*/React.createElement("aside", {
    style: {
      width: 252,
      flex: "none",
      borderRight: "1px solid var(--border-subtle)",
      background: "var(--surface-panel)",
      padding: "20px 16px",
      display: "flex",
      flexDirection: "column",
      gap: 16,
      overflow: "auto"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 12,
      fontWeight: 700,
      letterSpacing: "0.05em",
      textTransform: "uppercase",
      color: "var(--text-tertiary)"
    }
  }, "Source image"), /*#__PURE__*/React.createElement("image-slot", {
    id: "wf-src",
    style: {
      width: "100%",
      height: 150,
      display: "block"
    },
    shape: "rounded",
    radius: "12",
    placeholder: "Drop a 2D image"
  }), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 12,
      fontWeight: 600,
      color: "var(--text-secondary)",
      marginBottom: 8
    }
  }, "Describe the world"), /*#__PURE__*/React.createElement(W.Textarea, {
    value: prompt,
    onChange: e => setPrompt(e.target.value),
    rows: 3,
    placeholder: "A misty valley town at golden hour, walkable in first person\u2026"
  })), /*#__PURE__*/React.createElement(W.Button, {
    fullWidth: true,
    onClick: onGenerate,
    disabled: busy,
    iconLeft: /*#__PURE__*/React.createElement(Icon, {
      n: "sparkles",
      s: 16
    })
  }, busy ? "Building world…" : generated ? "Regenerate world" : "Generate 3D world"), /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: "auto",
      fontSize: 12,
      lineHeight: 1.5,
      color: "var(--text-tertiary)"
    }
  }, "Tyndall lifts a flat image into layered depth, fills occluded geometry, and rigs it for real-time physics."));
}

// ---------- app shell ----------
function App() {
  const [busy, setBusy] = React.useState(false);
  const [generated, setGenerated] = React.useState(false);
  const [spin, setSpin] = React.useState(false);
  const [depth, setDepth] = React.useState(72);
  const [physics, setPhysics] = React.useState(false);
  const [collide, setCollide] = React.useState(true);
  const [prompt, setPrompt] = React.useState("A misty valley town at golden hour, walkable in first person.");
  React.useEffect(() => {
    setTimeout(() => window.lucide && window.lucide.createIcons(), 40);
  });
  const generate = () => {
    setBusy(true);
    setGenerated(false);
    setTimeout(() => {
      setBusy(false);
      setGenerated(true);
      setSpin(true);
    }, 1100);
  };
  return /*#__PURE__*/React.createElement("div", {
    style: {
      height: "100%",
      display: "flex",
      flexDirection: "column",
      background: "var(--surface-canvas)"
    }
  }, /*#__PURE__*/React.createElement("header", {
    style: {
      height: 56,
      flex: "none",
      display: "flex",
      alignItems: "center",
      gap: 12,
      padding: "0 18px",
      borderBottom: "1px solid var(--border-subtle)"
    }
  }, /*#__PURE__*/React.createElement("img", {
    src: "../../assets/brand-mark.svg",
    style: {
      width: 22
    },
    alt: ""
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: "var(--font-serif)",
      fontSize: 18,
      fontWeight: 500
    }
  }, "Worldforge"), /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--text-tertiary)"
    }
  }, "/"), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 14,
      color: "var(--text-secondary)"
    }
  }, "valley-town"), /*#__PURE__*/React.createElement(W.Badge, {
    tone: "accent",
    size: "sm"
  }, "Beta"), /*#__PURE__*/React.createElement("div", {
    style: {
      marginLeft: "auto",
      display: "flex",
      alignItems: "center",
      gap: 8
    }
  }, /*#__PURE__*/React.createElement(W.Button, {
    variant: "ghost",
    size: "sm",
    iconLeft: /*#__PURE__*/React.createElement(Icon, {
      n: "play",
      s: 15
    })
  }, "Preview"), /*#__PURE__*/React.createElement(W.Button, {
    size: "sm",
    iconLeft: /*#__PURE__*/React.createElement(Icon, {
      n: "share",
      s: 15
    })
  }, "Share"))), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      display: "flex",
      minHeight: 0
    }
  }, /*#__PURE__*/React.createElement(SourcePanel, {
    onGenerate: generate,
    busy: busy,
    generated: generated,
    prompt: prompt,
    setPrompt: setPrompt
  }), /*#__PURE__*/React.createElement(Viewport, {
    generated: generated,
    spin: spin,
    physics: physics && generated
  }), /*#__PURE__*/React.createElement(Controls, {
    depth: depth,
    setDepth: setDepth,
    physics: physics,
    setPhysics: setPhysics,
    collide: collide,
    setCollide: setCollide
  })));
}
Object.assign(window, {
  App
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/worldforge/app.jsx", error: String((e && e.message) || e) }); }

// ui_kits/worldforge/image-slot.js
try { (() => {
// @ds-adherence-ignore -- omelette starter scaffold (raw elements/hex/px by design)
/* BEGIN USAGE */
/**
 * <image-slot> — user-fillable image placeholder.
 *
 * Drop this into a deck, mockup, or page wherever you want the user to
 * supply an image. You control the slot's shape and size; the user fills it
 * by dragging an image file onto it (or clicking to browse). The dropped
 * image persists across reloads via a .image-slots.state.json sidecar —
 * same read-via-fetch / write-via-window.omelette pattern as
 * design_canvas.jsx, so the filled slot shows on share links, downloaded
 * zips, and PPTX export. Outside the omelette runtime the slot is read-only.
 *
 * The host bridge only allows sidecar writes at the project root, so the
 * HTML that uses this component is assumed to live at the project root too
 * (same constraint as design_canvas.jsx).
 *
 * Attributes:
 *   id           Persistence key. REQUIRED for the drop to survive reload —
 *                every slot on the page needs a distinct id.
 *   shape        'rect' | 'rounded' | 'circle' | 'pill'   (default 'rounded')
 *                'circle' applies 50% border-radius; on a non-square slot
 *                that's an ellipse — set equal width and height for a true
 *                circle.
 *   radius       Corner radius in px for 'rounded'.       (default 12)
 *   mask         Any CSS clip-path value. Overrides `shape` — use this for
 *                hexagons, blobs, arbitrary polygons.
 *   fit          object-fit: cover | contain | fill.       (default 'cover')
 *                With cover (the default) double-clicking the filled slot
 *                enters a reframe mode: the whole image spills past the mask
 *                (translucent outside, opaque inside), drag to reposition,
 *                corner-drag to scale. The crop persists alongside the image
 *                in the sidecar. contain/fill stay static.
 *   position     object-position for fit=contain|fill.     (default '50% 50%')
 *   placeholder  Empty-state caption.                      (default 'Drop an image')
 *   src          Optional initial/fallback image URL. A user drop overrides
 *                it; clearing the drop reveals src again.
 *
 * Size and layout come from ordinary CSS on the element — width/height
 * inline or from a parent grid — so it composes with any layout.
 *
 * Usage:
 *   <image-slot id="hero"   style="width:800px;height:450px" shape="rounded" radius="20"
 *               placeholder="Drop a hero image"></image-slot>
 *   <image-slot id="avatar" style="width:120px;height:120px" shape="circle"></image-slot>
 *   <image-slot id="kite"   style="width:300px;height:300px"
 *               mask="polygon(50% 0, 100% 50%, 50% 100%, 0 50%)"></image-slot>
 */
/* END USAGE */

(() => {
  const STATE_FILE = '.image-slots.state.json';
  // 2× a ~600px slot in a 1920-wide deck — retina-sharp without making the
  // sidecar enormous. A 1200px WebP at q=0.85 is ~150-300KB.
  const MAX_DIM = 1200;
  // Raster formats only. SVG is excluded (can carry script; createImageBitmap
  // on SVG blobs is inconsistent). GIF is excluded because the canvas
  // re-encode keeps only the first frame, so an animated GIF would silently
  // go still — better to reject than surprise.
  const ACCEPT = ['image/png', 'image/jpeg', 'image/webp', 'image/avif'];

  // ── Shared sidecar store ────────────────────────────────────────────────
  // One fetch + immediate write-on-change for every <image-slot> on the
  // page. Reads via fetch() so viewing works anywhere the HTML and sidecar
  // are served together; writes go through window.omelette.writeFile, which
  // the host allowlists to *.state.json basenames only.
  const subs = new Set();
  let slots = {};
  // ids explicitly cleared before the sidecar fetch resolved — otherwise
  // the merge below can't tell "never set" from "just deleted" and would
  // resurrect the sidecar's stale value.
  const tombstones = new Set();
  let loaded = false;
  let loadP = null;
  function load() {
    if (loadP) return loadP;
    loadP = fetch(STATE_FILE).then(r => r.ok ? r.json() : null).then(j => {
      // Merge: sidecar loses to any in-memory change that raced ahead of
      // the fetch (drop or clear) so neither is clobbered by hydration.
      if (j && typeof j === 'object') {
        const merged = Object.assign({}, j, slots);
        // A framing-only write that raced ahead of hydration must not
        // drop a user image that's only on disk — inherit u from the
        // sidecar for any in-memory entry that lacks one.
        for (const k in slots) {
          if (merged[k] && !merged[k].u && j[k]) {
            merged[k].u = typeof j[k] === 'string' ? j[k] : j[k].u;
          }
        }
        for (const id of tombstones) delete merged[id];
        slots = merged;
      }
      tombstones.clear();
    }).catch(() => {}).then(() => {
      loaded = true;
      subs.forEach(fn => fn());
    });
    return loadP;
  }

  // Serialize writes so two near-simultaneous drops on different slots
  // can't reorder at the backend and leave the sidecar with only the
  // first. A save requested mid-flight just marks dirty and re-fires on
  // completion with the then-current slots.
  let saving = false;
  let saveDirty = false;
  function save() {
    if (saving) {
      saveDirty = true;
      return;
    }
    const w = window.omelette && window.omelette.writeFile;
    if (!w) return;
    saving = true;
    Promise.resolve(w(STATE_FILE, JSON.stringify(slots))).catch(() => {}).then(() => {
      saving = false;
      if (saveDirty) {
        saveDirty = false;
        save();
      }
    });
  }
  const S_MAX = 5;
  const clampS = s => Math.max(1, Math.min(S_MAX, s));

  // Normalize a stored slot value. Pre-reframe sidecars stored a bare
  // data-URL string; newer ones store {u, s, x, y}. Either shape is valid.
  function getSlot(id) {
    const v = slots[id];
    if (!v) return null;
    return typeof v === 'string' ? {
      u: v,
      s: 1,
      x: 0,
      y: 0
    } : v;
  }
  function setSlot(id, val) {
    if (!id) return;
    if (val) {
      slots[id] = val;
      tombstones.delete(id);
    } else {
      delete slots[id];
      if (!loaded) tombstones.add(id);
    }
    subs.forEach(fn => fn());
    // A drop is rare + high-value — write immediately so nav-away can't lose
    // it. Gate on the initial read so we don't overwrite a sidecar we haven't
    // merged yet; the merge in load() keeps this change once the read lands.
    if (loaded) save();else load().then(save);
  }

  // ── Image downscale ─────────────────────────────────────────────────────
  // Encode through a canvas so the sidecar carries resized bytes, not the
  // raw upload. Longest side is capped at 2× the slot's rendered width
  // (retina) and at MAX_DIM. WebP keeps alpha and is ~10× smaller than PNG
  // for photos, so there's no need for per-image format picking.
  async function toDataUrl(file, targetW) {
    const bitmap = await createImageBitmap(file);
    try {
      const cap = Math.min(MAX_DIM, Math.max(1, Math.round(targetW * 2)) || MAX_DIM);
      const scale = Math.min(1, cap / Math.max(bitmap.width, bitmap.height));
      const w = Math.max(1, Math.round(bitmap.width * scale));
      const h = Math.max(1, Math.round(bitmap.height * scale));
      const canvas = document.createElement('canvas');
      canvas.width = w;
      canvas.height = h;
      canvas.getContext('2d').drawImage(bitmap, 0, 0, w, h);
      return canvas.toDataURL('image/webp', 0.85);
    } finally {
      bitmap.close && bitmap.close();
    }
  }

  // ── Custom element ──────────────────────────────────────────────────────
  const stylesheet = ':host{display:inline-block;position:relative;vertical-align:top;' + '  font:13px/1.3 system-ui,-apple-system,sans-serif;color:rgba(0,0,0,.55);width:240px;height:160px}' + '.frame{position:absolute;inset:0;overflow:hidden;background:rgba(0,0,0,.04)}' +
  // .frame img (clipped) and .spill (unclipped ghost + handles) share the
  // same left/top/width/height in frame-%, computed by _applyView(), so the
  // inside-mask crop and the outside-mask spill stay pixel-aligned.
  '.frame img{position:absolute;max-width:none;transform:translate(-50%,-50%);' + '  -webkit-user-drag:none;user-select:none;touch-action:none}' +
  // Reframe mode (double-click): the full image spills past the mask. The
  // spill layer is sized to the IMAGE bounds so its corners are where the
  // resize handles belong. The ghost <img> inside is translucent; the real
  // clipped <img> underneath shows the opaque in-mask crop.
  '.spill{position:absolute;transform:translate(-50%,-50%);display:none;z-index:1;' + '  cursor:grab;touch-action:none}' + ':host([data-panning]) .spill{cursor:grabbing}' + '.spill .ghost{position:absolute;inset:0;width:100%;height:100%;opacity:.35;' + '  pointer-events:none;-webkit-user-drag:none;user-select:none;' + '  box-shadow:0 0 0 1px rgba(0,0,0,.2),0 12px 32px rgba(0,0,0,.2)}' + '.spill .handle{position:absolute;width:12px;height:12px;border-radius:50%;' + '  background:#fff;box-shadow:0 0 0 1.5px #c96442,0 1px 3px rgba(0,0,0,.3);' + '  transform:translate(-50%,-50%)}' + '.spill .handle[data-c=nw]{left:0;top:0;cursor:nwse-resize}' + '.spill .handle[data-c=ne]{left:100%;top:0;cursor:nesw-resize}' + '.spill .handle[data-c=sw]{left:0;top:100%;cursor:nesw-resize}' + '.spill .handle[data-c=se]{left:100%;top:100%;cursor:nwse-resize}' + ':host([data-reframe]){z-index:10}' + ':host([data-reframe]) .spill{display:block}' + ':host([data-reframe]) .frame{box-shadow:0 0 0 2px #c96442}' + '.empty{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;' + '  justify-content:center;gap:6px;text-align:center;padding:12px;box-sizing:border-box;' + '  cursor:pointer;user-select:none}' + '.empty svg{opacity:.45}' + '.empty .cap{max-width:90%;font-weight:500;letter-spacing:.01em}' + '.empty .sub{font-size:11px}' + '.empty .sub u{text-underline-offset:2px;text-decoration-color:rgba(0,0,0,.25)}' + '.empty:hover .sub u{color:rgba(0,0,0,.75);text-decoration-color:currentColor}' + ':host([data-over]) .frame{outline:2px solid #c96442;outline-offset:-2px;' + '  background:rgba(201,100,66,.10)}' + '.ring{position:absolute;inset:0;pointer-events:none;border:1.5px dashed rgba(0,0,0,.25);' + '  transition:border-color .12s}' + ':host([data-over]) .ring{border-color:#c96442}' + ':host([data-filled]) .ring{display:none}' +
  // Controls sit BELOW the mask (top:100%), absolutely positioned so the
  // author-declared slot height is unaffected. The gap is padding, not a
  // top offset, so the hover target stays contiguous with the frame.
  '.ctl{position:absolute;top:100%;left:50%;transform:translateX(-50%);padding-top:8px;' + '  display:flex;gap:6px;opacity:0;pointer-events:none;transition:opacity .12s;z-index:2;' + '  white-space:nowrap}' + ':host([data-filled][data-editable]:hover) .ctl,:host([data-reframe]) .ctl' + '  {opacity:1;pointer-events:auto}' + '.ctl button{appearance:none;border:0;border-radius:6px;padding:5px 10px;cursor:pointer;' + '  background:rgba(0,0,0,.65);color:#fff;font:11px/1 system-ui,-apple-system,sans-serif;' + '  backdrop-filter:blur(6px)}' + '.ctl button:hover{background:rgba(0,0,0,.8)}' + '.err{position:absolute;left:8px;bottom:8px;right:8px;color:#b3261e;font-size:11px;' + '  background:rgba(255,255,255,.85);padding:4px 6px;border-radius:5px;pointer-events:none}';
  const icon = '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' + 'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">' + '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/>' + '<path d="m21 15-5-5L5 21"/></svg>';
  class ImageSlot extends HTMLElement {
    static get observedAttributes() {
      return ['shape', 'radius', 'mask', 'fit', 'position', 'placeholder', 'src', 'id'];
    }
    constructor() {
      super();
      const root = this.attachShadow({
        mode: 'open'
      });
      // .spill and .ctl sit OUTSIDE .frame so overflow:hidden + border-radius
      // on the frame (circle, pill, rounded) can't clip them.
      root.innerHTML = '<style>' + stylesheet + '</style>' + '<div class="frame" part="frame">' + '  <img part="image" alt="" draggable="false" style="display:none">' + '  <div class="empty" part="empty">' + icon + '    <div class="cap"></div>' + '    <div class="sub">or <u>browse files</u></div></div>' + '  <div class="ring" part="ring"></div>' + '</div>' + '<div class="spill">' + '  <img class="ghost" alt="" draggable="false">' + '  <div class="handle" data-c="nw"></div><div class="handle" data-c="ne"></div>' + '  <div class="handle" data-c="sw"></div><div class="handle" data-c="se"></div>' + '</div>' + '<div class="ctl"><button data-act="replace" title="Replace image">Replace</button>' + '  <button data-act="clear" title="Remove image">Remove</button></div>' + '<input type="file" accept="' + ACCEPT.join(',') + '" hidden>';
      this._frame = root.querySelector('.frame');
      this._ring = root.querySelector('.ring');
      this._img = root.querySelector('.frame img');
      this._empty = root.querySelector('.empty');
      this._cap = root.querySelector('.cap');
      this._sub = root.querySelector('.sub');
      this._spill = root.querySelector('.spill');
      this._ghost = root.querySelector('.ghost');
      this._err = null;
      this._input = root.querySelector('input');
      this._depth = 0;
      this._gen = 0;
      this._view = {
        s: 1,
        x: 0,
        y: 0
      };
      this._subFn = () => this._render();
      // Shadow-DOM listeners live with the shadow DOM — bound once here so
      // disconnect/reconnect (e.g. React remount) doesn't stack handlers.
      this._empty.addEventListener('click', () => this._input.click());
      root.addEventListener('click', e => {
        const act = e.target && e.target.getAttribute && e.target.getAttribute('data-act');
        if (act === 'replace') {
          this._exitReframe(true);
          this._input.click();
        }
        if (act === 'clear') {
          this._exitReframe(false);
          this._gen++;
          this._local = null;
          if (this.id) setSlot(this.id, null);else this._render();
        }
      });
      this._input.addEventListener('change', () => {
        const f = this._input.files && this._input.files[0];
        if (f) this._ingest(f);
        this._input.value = '';
      });
      // naturalWidth/Height aren't known until load — re-apply so the cover
      // baseline is computed from real dimensions, not the 100%×100% fallback.
      this._img.addEventListener('load', () => this._applyView());
      // Gated on editable + fit=cover so share links and contain/fill slots
      // stay static.
      this.addEventListener('dblclick', e => {
        if (!this.hasAttribute('data-editable') || !this._reframes()) return;
        e.preventDefault();
        if (this.hasAttribute('data-reframe')) this._exitReframe(true);else this._enterReframe();
      });
      // Pan + resize both originate on the spill layer. A handle pointerdown
      // drives an aspect-locked resize anchored at the opposite corner; any
      // other pointerdown on the spill pans. Offsets are frame-% so a
      // reframed slot survives responsive resize / PPTX export.
      this._spill.addEventListener('pointerdown', e => {
        if (e.button !== 0 || !this.hasAttribute('data-reframe')) return;
        e.preventDefault();
        e.stopPropagation();
        this._spill.setPointerCapture(e.pointerId);
        const rect = this.getBoundingClientRect();
        const fw = rect.width || 1,
          fh = rect.height || 1;
        const corner = e.target.getAttribute && e.target.getAttribute('data-c');
        let move;
        if (corner) {
          // Resize about the OPPOSITE corner. Viewport-px throughout (rect
          // fw/fh, not clientWidth) so the math survives a transform:scale()
          // ancestor — deck_stage renders slides scaled-to-fit.
          const iw = this._img.naturalWidth || 1,
            ih = this._img.naturalHeight || 1;
          const base = Math.max(fw / iw, fh / ih);
          const sx = corner.includes('e') ? 1 : -1;
          const sy = corner.includes('s') ? 1 : -1;
          const s0 = this._view.s;
          const w0 = iw * base * s0,
            h0 = ih * base * s0;
          const cx0 = (50 + this._view.x) / 100 * fw;
          const cy0 = (50 + this._view.y) / 100 * fh;
          const ox = cx0 - sx * w0 / 2,
            oy = cy0 - sy * h0 / 2;
          const diag0 = Math.hypot(w0, h0);
          const ux = sx * w0 / diag0,
            uy = sy * h0 / diag0;
          move = ev => {
            const proj = (ev.clientX - rect.left - ox) * ux + (ev.clientY - rect.top - oy) * uy;
            const s = clampS(s0 * proj / diag0);
            const d = diag0 * s / s0;
            this._view.s = s;
            this._view.x = (ox + ux * d / 2) / fw * 100 - 50;
            this._view.y = (oy + uy * d / 2) / fh * 100 - 50;
            this._clampView();
            this._applyView();
          };
        } else {
          this.setAttribute('data-panning', '');
          const start = {
            px: e.clientX,
            py: e.clientY,
            x: this._view.x,
            y: this._view.y
          };
          move = ev => {
            this._view.x = start.x + (ev.clientX - start.px) / fw * 100;
            this._view.y = start.y + (ev.clientY - start.py) / fh * 100;
            this._clampView();
            this._applyView();
          };
        }
        const up = () => {
          try {
            this._spill.releasePointerCapture(e.pointerId);
          } catch {}
          this._spill.removeEventListener('pointermove', move);
          this._spill.removeEventListener('pointerup', up);
          this._spill.removeEventListener('pointercancel', up);
          this.removeAttribute('data-panning');
          this._dragUp = null;
        };
        // Stashed so _exitReframe (Escape / outside-click mid-drag) can
        // tear the capture + listeners down synchronously.
        this._dragUp = up;
        this._spill.addEventListener('pointermove', move);
        this._spill.addEventListener('pointerup', up);
        this._spill.addEventListener('pointercancel', up);
      });
      // Wheel zoom stays available inside reframe mode as a trackpad nicety —
      // zooms toward the cursor (offset' = cursor·(1-k) + offset·k).
      this.addEventListener('wheel', e => {
        if (!this.hasAttribute('data-reframe')) return;
        e.preventDefault();
        const r = this.getBoundingClientRect();
        const cx = (e.clientX - r.left) / r.width * 100 - 50;
        const cy = (e.clientY - r.top) / r.height * 100 - 50;
        const prev = this._view.s;
        const next = clampS(prev * Math.pow(1.0015, -e.deltaY));
        if (next === prev) return;
        const k = next / prev;
        this._view.s = next;
        this._view.x = cx * (1 - k) + this._view.x * k;
        this._view.y = cy * (1 - k) + this._view.y * k;
        this._clampView();
        this._applyView();
      }, {
        passive: false
      });
    }
    connectedCallback() {
      // Warn once per page — an id-less slot works for the session but
      // cannot persist, and two id-less slots would share nothing.
      if (!this.id && !ImageSlot._warned) {
        ImageSlot._warned = true;
        console.warn('<image-slot> without an id will not persist its dropped image.');
      }
      this.addEventListener('dragenter', this);
      this.addEventListener('dragover', this);
      this.addEventListener('dragleave', this);
      this.addEventListener('drop', this);
      subs.add(this._subFn);
      // width%/height% in _applyView encode the frame aspect at call time —
      // a host resize (responsive grid, pane divider) would stretch the
      // image until the next _render. Re-render on size change: _render()
      // re-seeds _view from stored before clamp/apply, so a shrink→grow
      // cycle round-trips instead of ratcheting x/y toward the narrower
      // frame's clamp range.
      this._ro = new ResizeObserver(() => this._render());
      this._ro.observe(this);
      load();
      this._render();
    }
    disconnectedCallback() {
      subs.delete(this._subFn);
      this.removeEventListener('dragenter', this);
      this.removeEventListener('dragover', this);
      this.removeEventListener('dragleave', this);
      this.removeEventListener('drop', this);
      if (this._ro) {
        this._ro.disconnect();
        this._ro = null;
      }
      this._exitReframe(false);
    }
    _enterReframe() {
      if (this.hasAttribute('data-reframe')) return;
      this.setAttribute('data-reframe', '');
      this._applyView();
      // Close on click outside (the spill handler stopPropagation()s so
      // in-image drags don't reach this) and on Escape. Listeners are held
      // on the instance so _exitReframe / disconnectedCallback can detach
      // exactly what was attached.
      this._outside = e => {
        if (e.composedPath && e.composedPath().includes(this)) return;
        this._exitReframe(true);
      };
      this._esc = e => {
        if (e.key === 'Escape') this._exitReframe(true);
      };
      document.addEventListener('pointerdown', this._outside, true);
      document.addEventListener('keydown', this._esc, true);
    }
    _exitReframe(commit) {
      if (!this.hasAttribute('data-reframe')) return;
      if (this._dragUp) this._dragUp();
      this.removeAttribute('data-reframe');
      this.removeAttribute('data-panning');
      if (this._outside) document.removeEventListener('pointerdown', this._outside, true);
      if (this._esc) document.removeEventListener('keydown', this._esc, true);
      this._outside = this._esc = null;
      if (commit) this._commitView();
    }
    attributeChangedCallback() {
      if (this.shadowRoot) this._render();
    }

    // handleEvent — one listener object for all four drag events keeps the
    // add/remove symmetric and the depth counter correct.
    handleEvent(e) {
      if (e.type === 'dragenter' || e.type === 'dragover') {
        // Without preventDefault the browser never fires 'drop'.
        e.preventDefault();
        e.stopPropagation();
        if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy';
        if (e.type === 'dragenter') this._depth++;
        this.setAttribute('data-over', '');
      } else if (e.type === 'dragleave') {
        // dragenter/leave fire for every descendant crossing — count depth
        // so hovering the icon inside the empty state doesn't flicker.
        if (--this._depth <= 0) {
          this._depth = 0;
          this.removeAttribute('data-over');
        }
      } else if (e.type === 'drop') {
        e.preventDefault();
        e.stopPropagation();
        this._depth = 0;
        this.removeAttribute('data-over');
        const f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
        if (f) this._ingest(f);
      }
    }
    async _ingest(file) {
      this._setError(null);
      if (!file || ACCEPT.indexOf(file.type) < 0) {
        this._setError('Drop a PNG, JPEG, WebP, or AVIF image.');
        return;
      }
      // toDataUrl can take hundreds of ms on a large photo. A Clear or a
      // newer drop during that window would be clobbered when this await
      // resumes — bump + capture a generation so stale encodes bail.
      const gen = ++this._gen;
      try {
        const w = this.clientWidth || this.offsetWidth || MAX_DIM;
        const url = await toDataUrl(file, w);
        if (gen !== this._gen) return;
        // Only exit reframe once the new image is in hand — a rejected type
        // or decode failure leaves the in-progress crop untouched.
        this._exitReframe(false);
        const val = {
          u: url,
          s: 1,
          x: 0,
          y: 0
        };
        setSlot(this.id || '', val);
        // Keep a session-local copy for id-less slots so the drop still
        // shows, even though it cannot persist.
        if (!this.id) {
          this._local = val;
          this._render();
        }
      } catch (err) {
        if (gen !== this._gen) return;
        this._setError('Could not read that image.');
        console.warn('<image-slot> ingest failed:', err);
      }
    }
    _setError(msg) {
      if (this._err) {
        this._err.remove();
        this._err = null;
      }
      if (!msg) return;
      const d = document.createElement('div');
      d.className = 'err';
      d.textContent = msg;
      this.shadowRoot.appendChild(d);
      this._err = d;
      setTimeout(() => {
        if (this._err === d) {
          d.remove();
          this._err = null;
        }
      }, 3000);
    }

    // Reframing (pan/resize) is only meaningful for fit=cover — contain/fill
    // keep the old object-fit path and double-click is a no-op.
    _reframes() {
      return this.hasAttribute('data-filled') && (this.getAttribute('fit') || 'cover') === 'cover';
    }

    // Cover-baseline geometry, shared by clamp/apply/resize. Null until the
    // img has loaded (naturalWidth is 0 before that) or when the slot has no
    // layout box — ResizeObserver fires with a 0×0 rect under display:none,
    // and clamping against a degenerate 1×1 frame would silently pull the
    // stored pan toward zero.
    _geom() {
      const iw = this._img.naturalWidth,
        ih = this._img.naturalHeight;
      const fw = this.clientWidth,
        fh = this.clientHeight;
      if (!iw || !ih || !fw || !fh) return null;
      return {
        iw,
        ih,
        fw,
        fh,
        base: Math.max(fw / iw, fh / ih)
      };
    }
    _clampView() {
      // Pan range on each axis is half the overflow past the frame edge.
      const g = this._geom();
      if (!g) return;
      const mx = Math.max(0, (g.iw * g.base * this._view.s / g.fw - 1) * 50);
      const my = Math.max(0, (g.ih * g.base * this._view.s / g.fh - 1) * 50);
      this._view.x = Math.max(-mx, Math.min(mx, this._view.x));
      this._view.y = Math.max(-my, Math.min(my, this._view.y));
    }
    _applyView() {
      const g = this._geom();
      const fit = this.getAttribute('fit') || 'cover';
      if (fit !== 'cover' || !g) {
        // Non-cover, or dimensions not known yet (before img load).
        this._img.style.width = '100%';
        this._img.style.height = '100%';
        this._img.style.left = '50%';
        this._img.style.top = '50%';
        this._img.style.objectFit = fit;
        this._img.style.objectPosition = this.getAttribute('position') || '50% 50%';
        return;
      }
      // Cover baseline: img fills the frame on its tighter axis at s=1, so
      // pan works immediately on the overflowing axis without zooming first.
      // Width/height and left/top are all frame-% — depends only on the
      // frame aspect ratio, so a responsive resize keeps the same crop. The
      // spill layer mirrors the same box so its corners = image corners.
      const k = g.base * this._view.s;
      const w = g.iw * k / g.fw * 100 + '%';
      const h = g.ih * k / g.fh * 100 + '%';
      const l = 50 + this._view.x + '%';
      const t = 50 + this._view.y + '%';
      this._img.style.width = w;
      this._img.style.height = h;
      this._img.style.left = l;
      this._img.style.top = t;
      this._img.style.objectFit = '';
      this._spill.style.width = w;
      this._spill.style.height = h;
      this._spill.style.left = l;
      this._spill.style.top = t;
    }
    _commitView() {
      const v = {
        s: this._view.s,
        x: this._view.x,
        y: this._view.y
      };
      if (this._userUrl) v.u = this._userUrl;
      // Framing-only (no u) persists too so an author-src slot remembers its
      // crop; clearing the sidecar still falls through to src=.
      if (this.id) setSlot(this.id, v);else {
        this._local = v;
      }
    }
    _render() {
      // Shape / mask. Presets use border-radius so the dashed ring can
      // follow the rounded outline; clip-path is only applied for an
      // explicit `mask` (the ring is hidden there since a rectangle
      // dashed border chopped by an arbitrary polygon looks broken).
      const mask = this.getAttribute('mask');
      const shape = (this.getAttribute('shape') || 'rounded').toLowerCase();
      let radius = '';
      if (shape === 'circle') radius = '50%';else if (shape === 'pill') radius = '9999px';else if (shape === 'rounded') {
        const n = parseFloat(this.getAttribute('radius'));
        radius = (Number.isFinite(n) ? n : 12) + 'px';
      }
      this._frame.style.borderRadius = mask ? '' : radius;
      this._frame.style.clipPath = mask || '';
      this._ring.style.borderRadius = mask ? '' : radius;
      this._ring.style.display = mask ? 'none' : '';

      // Controls and reframe entry gate on this so share links stay read-only.
      const editable = !!(window.omelette && window.omelette.writeFile);
      this.toggleAttribute('data-editable', editable);
      this._sub.style.display = editable ? '' : 'none';

      // Content. The sidecar is also writable by the agent's write_file
      // tool, so its value isn't guaranteed canvas-originated — only accept
      // data:image/ URLs from it. The `src` attribute is author-controlled
      // (Claude wrote it into the HTML) so it passes through unchanged.
      let stored = this.id ? getSlot(this.id) : this._local;
      if (stored && stored.u && !/^data:image\//i.test(stored.u)) stored = null;
      const srcAttr = this.getAttribute('src') || '';
      this._userUrl = stored && stored.u || null;
      const url = this._userUrl || srcAttr;
      // Don't clobber an in-flight reframe with a store-triggered re-render.
      if (!this.hasAttribute('data-reframe')) {
        this._view = {
          s: stored && Number.isFinite(stored.s) ? clampS(stored.s) : 1,
          x: stored && Number.isFinite(stored.x) ? stored.x : 0,
          y: stored && Number.isFinite(stored.y) ? stored.y : 0
        };
      }
      this._cap.textContent = this.getAttribute('placeholder') || 'Drop an image';
      // Toggle via style.display — the [hidden] attribute alone loses to
      // the display:flex / display:block rules in the stylesheet above.
      if (url) {
        if (this._img.getAttribute('src') !== url) {
          this._img.src = url;
          this._ghost.src = url;
        }
        this._img.style.display = 'block';
        this._empty.style.display = 'none';
        this.setAttribute('data-filled', '');
        this._clampView();
        this._applyView();
      } else {
        this._img.style.display = 'none';
        this._img.removeAttribute('src');
        this._ghost.removeAttribute('src');
        this._empty.style.display = 'flex';
        this.removeAttribute('data-filled');
      }
    }
  }
  if (!customElements.get('image-slot')) {
    customElements.define('image-slot', ImageSlot);
  }
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/worldforge/image-slot.js", error: String((e && e.message) || e) }); }

__ds_ns.Avatar = __ds_scope.Avatar;

__ds_ns.Badge = __ds_scope.Badge;

__ds_ns.Button = __ds_scope.Button;

__ds_ns.Card = __ds_scope.Card;

__ds_ns.Checkbox = __ds_scope.Checkbox;

__ds_ns.Dialog = __ds_scope.Dialog;

__ds_ns.IconButton = __ds_scope.IconButton;

__ds_ns.Input = __ds_scope.Input;

__ds_ns.Radio = __ds_scope.Radio;

__ds_ns.Select = __ds_scope.Select;

__ds_ns.Switch = __ds_scope.Switch;

__ds_ns.Tabs = __ds_scope.Tabs;

__ds_ns.Tag = __ds_scope.Tag;

__ds_ns.Textarea = __ds_scope.Textarea;

__ds_ns.Tooltip = __ds_scope.Tooltip;

})();
