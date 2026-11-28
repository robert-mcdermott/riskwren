// Admin → Appearance: the organization's name, logo, palette, accent, and rating colors, with a
// live preview. What the configuration file's [branding] section sets is shown, and locked.

import { del, get, post, put, upload } from "../core/api.js";
import { button, h, icon } from "../core/dom.js";
import { titleCase } from "../core/format.js";
import { banner, checkbox, field, submit } from "../components/form.js";
import { toast } from "../components/toast.js";
import { alert, card, pageHeader, pill, ratingBadge } from "../components/ui.js";
import { show } from "./page.js";

// What each palette looks like, for the cards: page, surface, text, accent.
const SWATCHES = {
  wren: ["#faf9f6", "#ffffff", "#22252f", "#0d5a79", "#b85e31"],
  slate: ["#f6f8fb", "#ffffff", "#1c2333", "#2a4fc7", "#1a8a94"],
  garnet: ["#f9f8f8", "#ffffff", "#262223", "#8f1f2c", "#5b6472"],
};

function fixedSwatch(color) {
  const node = h("span", { class: "swatch", "aria-hidden": "true" });
  node.style.setProperty("background", color);
  return node;
}

function swatch(color) {
  const node = h("i");
  node.style.setProperty("background", color);
  return node;
}

function images(data, reload) {
  return card({ title: "Logo, tab icon, and sign-in picture" },
    h("p", { class: "muted" }, "PNG, JPEG, WebP, or SVG, up to 2 MB. With no logo, the product name is shown beside the wren. The sign-in picture fills the panel beside the sign-in form."),
    h("div", {}, data.images.map((image) => {
      const input = h("input", { type: "file", accept: "image/png,image/jpeg,image/webp,image/svg+xml", hidden: true,
        onchange: async () => {
          if (!input.files[0]) return;
          try {
            await upload(`/api/v1/admin/branding/images/${image.kind}`, input.files[0]);
            toast(`${image.label} was updated.`);
            window.dispatchEvent(new CustomEvent("riskwren:branding"));
            reload();
          } catch (error) {
            toast(Object.values(error.fields ?? {}).join(" ") || error.detail || "That image could not be used.");
          }
        } });
      const url = { "logo-light": data.logo_light, "logo-dark": image.set ? data.logo_dark : null, favicon: data.favicon, "sign-in": data.sign_in_image }[image.kind];
      return h("div", { class: "upload" },
        h("div", { class: "upload-thumb", "data-dark": String(image.kind === "logo-dark") },
          url ? h("img", { src: url, alt: "" }) : h("span", { class: "subtle" }, "None")),
        h("div", { class: "grow" }, h("div", { class: "cell-main" }, image.label),
          h("div", { class: "cell-sub" }, image.kind === "logo-dark" && !image.set && data.logo_light
            ? "Using the light-background logo." : image.from_file ? "Set in the configuration file." : image.set ? "Uploaded." : "Not set.")),
        input,
        image.from_file ? null : button(image.set ? "Replace" : "Upload", { kind: "btn-sm", iconName: "upload", onclick: () => input.click() }),
        image.set && !image.from_file ? button("Remove", { kind: "btn-sm btn-ghost", onclick: async () => {
          await del(`/api/v1/admin/branding/images/${image.kind}`);
          window.dispatchEvent(new CustomEvent("riskwren:branding"));
          reload();
        } }) : null);
    })));
}

export function adminAppearance(main) {
  return show(main, {
    title: "Appearance",
    load: async () => (await get("/api/v1/admin/branding", null, { fresh: true })).data,
    view: (data, reload) => {
      const product = field("Product name", { value: data.product_name, required: true,
        hint: "Shown in the sidebar, the browser tab, and email. Keep it short." });
      const organization = field("Organization", { value: data.organization_name,
        hint: "Your organization's name, shown on the sign-in page." });
      const powered = checkbox("Show “Powered by RiskWren”", { checked: data.show_powered_by,
        hint: "A small link at the foot of the sidebar when you use your own product name." });

      let palette = data.palette;
      const cards = h("div", { class: "palette-choice", role: "radiogroup", "aria-label": "Default palette" },
        data.palettes.map((option) => h("label", { class: "palette-card" },
          h("input", { type: "radio", name: "palette", value: option.key, checked: option.key === palette,
            onchange: () => {
              palette = option.key;
              drawPreview();
            } }),
          h("div", { class: "palette-swatches", "aria-hidden": "true" }, SWATCHES[option.key].map(swatch)),
          h("strong", {}, option.key), h("span", {}, option.description))));

      let ramp = data.rating_ramp;
      const ramps = h("div", { class: "stack-sm", role: "radiogroup", "aria-label": "Rating colors" },
        data.ramps.map((option) => h("label", { class: "check" },
          h("input", { type: "radio", name: "ramp", value: option.key, checked: option.key === ramp,
            onchange: () => {
              ramp = option.key;
              drawPreview();
            } }),
          h("span", {}, h("strong", {}, titleCase(option.key)), h("span", { class: "hint subtle" }, ` ${option.description}.`)))));

      const picker = h("input", { type: "color", class: "input input-color", "aria-label": "Pick an accent color",
        value: data.accent || SWATCHES[data.palette][3] });
      const accent = field("Accent color", { value: data.accent, placeholder: "The palette's own",
        hint: "Optional. Your brand color, as hex. It colors buttons, links, and the selected page." });
      const accentDark = field("Accent after dark", { value: data.accent_dark, placeholder: "Worked out from the accent",
        hint: "Optional. A lighter shade of your color for dark mode, as hex. Leave it empty and one is worked out." });
      const message = field("Message on the sign-in page", { type: "textarea", rows: 3, maxlength: 600, value: data.sign_in_message,
        hint: "Optional. Who to ask for access, or a line about your program." });
      const links = field("Links", { type: "textarea", rows: 4, value: (data.footer_links ?? []).map((link) => `${link.label} | ${link.url}`).join("\n"),
        hint: "Up to five, one to a line, as: Label | https://address. Shown at the foot of the sidebar and the sign-in page." });
      const emailFooter = field("Last line of every email", { value: data.email_footer, maxlength: 300,
        hint: "Optional. For example the name of your office and how to reach it." });
      const checks = h("div", { "aria-live": "polite" });
      const preview = h("div", { class: "preview" });

      let timer = null;
      let derived = null;
      const drawChecks = async () => {
        const value = accent.input.value.trim();
        if (!value) {
          derived = null;
          checks.replaceChildren();
          drawPreview();
          return;
        }
        try {
          const dark = accentDark.input.value.trim();
          derived = (await post("/api/v1/admin/branding/check", { accent: value, accent_dark: /^#[0-9a-f]{6}$/i.test(dark) ? dark : "" })).data;
          accent.setError(null);
          checks.replaceChildren(h("div", { class: "stack-sm" },
            derived.checks.map((c) => h("div", { class: "contrast-row" },
              pill(c.ok ? "Passes" : "Too low", c.ok ? "ok" : "danger"),
              h("span", { class: "grow" }, c.pair),
              h("span", { class: "numeric muted" }, `${c.ratio.toFixed(1)} : 1`)))));
        } catch (error) {
          derived = null;
          checks.replaceChildren();
          accent.setError(error.fields?.accent ?? error.detail);
        }
        drawPreview();
      };
      const drawPreview = () => {
        const sample = (modeName) => {
          const box = h("div", { class: "preview-mode", "data-mode": modeName, "data-palette": palette, "data-ramp": ramp },
            h("div", { class: "subtle" }, modeName === "light" ? "By day" : "After dark"),
            h("div", { class: "row-sm wrap" }, button("Save", { kind: "btn-primary", tabindex: "-1" }),
              h("a", { href: "#", tabindex: "-1", onclick: (event) => event.preventDefault() }, "A link"),
              pill("Within appetite", "ok")),
            h("div", { class: "row-sm wrap" }, ratingBadge(1, "Low"), ratingBadge(2, "Moderate"),
              ratingBadge(4, "High"), ratingBadge(5, "Critical")),
            h("div", { class: "nav-link", "aria-current": "page" }, icon("home"), "Selected page"));
          if (derived) {
            const pick = modeName === "light" ? [derived.day, derived.on_day] : [derived.night, derived.on_night];
            box.style.setProperty("--brand-accent", pick[0]);
            box.style.setProperty("--brand-accent-hover", pick[0]);
            box.style.setProperty("--brand-on-accent", pick[1]);
            box.style.setProperty("--brand-accent-soft", `color-mix(in oklch, ${pick[0]} 16%, transparent)`);
          } else {
            for (const name of ["--brand-accent", "--brand-accent-hover", "--brand-on-accent", "--brand-accent-soft"]) {
              box.style.setProperty(name, "initial");
            }
          }
          return box;
        };
        preview.replaceChildren(
          h("div", { class: "preview-bar" }, h("strong", {}, product.input.value || "Product name"),
            h("span", { class: "subtle" }, `${titleCase(palette)} palette`)),
          h("div", { class: "preview-body" }, h("div", { class: "preview-modes" }, sample("light"), sample("dark"))));
      };
      const changed = () => {
        clearTimeout(timer);
        timer = setTimeout(drawChecks, 250);
      };
      accent.input.addEventListener("input", () => {
        if (/^#[0-9a-f]{6}$/i.test(accent.input.value.trim())) picker.value = accent.input.value.trim();
        changed();
      });
      picker.addEventListener("input", () => {
        accent.input.value = picker.value;
        changed();
      });
      accentDark.input.addEventListener("input", changed);
      product.input.addEventListener("input", drawPreview);
      drawChecks();

      // What the configuration file sets cannot be changed here. It is shown, and locked.
      const pinned = new Set(data.pinned ?? []);
      const FROM_FILE = "Set in the configuration file.";
      const lock = (name, control) => {
        if (!pinned.has(name)) return;
        control.input.disabled = true;
        (control.node.classList.contains("check") ? control.node.lastChild : control.node).append(h("div", { class: "hint subtle" }, FROM_FILE));
      };
      lock("product_name", product);
      lock("organization_name", organization);
      lock("show_powered_by", powered);
      lock("accent", accent);
      lock("accent_dark", accentDark);
      lock("sign_in_message", message);
      lock("footer_links", links);
      lock("email_footer", emailFooter);
      if (pinned.has("accent")) picker.disabled = true;
      if (pinned.has("palette")) for (const radio of cards.querySelectorAll("input")) radio.disabled = true;
      if (pinned.has("rating_ramp")) for (const radio of ramps.querySelectorAll("input")) radio.disabled = true;
      const fixedColors = data.colors?.day ? card({ title: "Colors" }, h("div", { class: "stack" },
        h("p", { class: "muted" }, "Your organization's exact colors are set in the configuration file, by day and after dark. To change them, edit the [branding.colors] tables there and restart."),
        ["day", "night"].map((modeName) => h("div", { class: "stack-sm" },
          h("div", { class: "label" }, modeName === "day" ? "By day" : "After dark"),
          h("div", { class: "row-sm wrap" }, ["bg", "surface", "text", "muted", "border", "accent", "on_accent", "stripe"].map((name) =>
            h("span", { class: "row-sm" }, fixedSwatch(data.colors[modeName][name]),
              h("span", { class: "subtle" }, `${name.replace("_", " ")} ${data.colors[modeName][name]}`)))))))) : null;

      const problem = banner();
      const save = button("Save", { kind: "btn-primary", type: "submit" });
      const form = h("form", { class: "stack-lg", novalidate: true, onsubmit: async (event) => {
        event.preventDefault();
        const done = await submit({ button: save, banner: problem,
          fields: { product_name: product, organization_name: organization, accent, accent_dark: accentDark, sign_in_message: message,
            footer_links: links, email_footer: emailFooter },
          run: () => put("/api/v1/admin/branding", { product_name: product.input.value,
            organization_name: organization.input.value, palette, accent: accent.input.value.trim(),
            accent_dark: accentDark.input.value.trim(), rating_ramp: ramp, show_powered_by: powered.input.checked,
            sign_in_message: message.input.value, email_footer: emailFooter.input.value,
            footer_links: links.input.value.split("\n").map((line) => line.trim()).filter(Boolean).map((line) => {
              const cut = line.indexOf("|");
              return cut < 0 ? { label: line, url: "" } : { label: line.slice(0, cut).trim(), url: line.slice(cut + 1).trim() };
            }) }) });
        if (done) {
          toast("The appearance was saved.");
          window.dispatchEvent(new CustomEvent("riskwren:branding"));
          reload();
        }
      } },
      problem,
      card({ title: "Names" }, h("div", { class: "stack" }, product.node, organization.node, powered.node)),
      fixedColors ?? card({ title: "Colors" }, h("div", { class: "stack-lg" },
        h("div", { class: "stack-sm" }, h("div", { class: "label" }, "Default palette"),
          h("p", { class: "hint subtle" }, "What everyone sees unless they choose another for themselves."), cards),
        h("div", { class: "stack-sm" }, accent.node,
          h("div", { class: "row" }, picker,
            button("Use the palette's own", { kind: "btn-ghost btn-sm", onclick: () => {
              accent.input.value = "";
              drawChecks();
            } })),
          checks, accentDark.node))),
      card({ title: "Rating colors" }, h("div", { class: "stack-sm" },
        h("p", { class: "hint subtle" }, "How Low to Critical are colored, on badges and the heat map. A rating always carries its bars and its name as well."),
        ramps)),
      card({ title: "Sign-in page, links, and email" }, h("div", { class: "stack" }, message.node, links.node, emailFooter.node)),
      h("div", { class: "form-actions" }, save, h("span", { class: "subtle" }, "Changes apply for everyone as soon as you save.")));

      return h("div", { class: "stack-lg" },
        pageHeader({ eyebrow: "Admin", title: "Appearance",
          lede: "Make it yours: your name, your logo, your colors. Every color is checked for readability before it can be saved." }),
        pinned.size ? alert("info", icon("info"), h("div", {}, h("strong", {}, "Some of this is set in the configuration file. "),
          "Those settings are shown here and can be changed only in the file. Everything else is yours to change.")) : null,
        h("div", { class: "split" },
          form,
          h("div", { class: "stack-lg" },
            fixedColors ? null : card({ title: "Preview" }, h("div", { class: "stack" }, preview,
              alert("info", icon("info"), h("div", {}, "The preview shows your choices before you save them.")))),
            images(data, reload))));
    },
  });
}
