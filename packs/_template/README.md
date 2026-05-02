# Pack Template

Copy this folder, rename it after the machine class (`cnc_3axis`, `bottle_filler`, …), and customize.

## Steps

1. **Copy:** `cp -r packs/_template packs/<your_machine_class>`
2. **Edit `pack_manifest.json`:** set `pack_id`, `version`, `machine_class`, supported brands, default steps
3. **Customize `machine_config.yaml.sample`:** define typical step names + expected cycle times
4. **Add PLC templates:** drop SCL/ST files into `plc_templates/<brand>/` for each brand the pack supports
5. **Define dashboards:** `dashboards/default_layout.json` describes which widgets to show out-of-the-box
6. **Test locally:** `python main.py --pack <your_machine_class>` should load the pack at startup
7. **Submit:** PR to platform repo (DS-shipped packs) OR keep in customer repo (`packs/customer_<name>/` is gitignored)

## Required files

| File | Required | Purpose |
|---|---|---|
| `pack_manifest.json` | ✅ | Discovery metadata |
| `README.md` | ✅ | What this pack ships, when to use it |
| `machine_config.yaml.sample` | ✅ | Engineer's starting point — copy to `config/machines/` |
| `plc_templates/<brand>/FB_CycleMaster.<ext>` | at least 1 | Wired PLC code for that machine class |
| `dashboards/default_layout.json` | ⚠️ recommended | Which UI widgets matter for this machine |
