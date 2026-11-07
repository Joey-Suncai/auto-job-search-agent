# SuccessFactors job page: the company's own application wizard (JSA-222, KB Signaling 2026-11-05)

`custom_apply_widget(info)` decides, on a SuccessFactors-hosted job page, whether the visible "Apply now" belongs to the
company's own application wizard instead of the SAP SuccessFactors form. `info` = {"sap": [{"href": str, "visible":
bool}], "shadow": bool}: `sap` lists every link on the page whose href contains "/talentcommunity/apply/" (the SAP
apply link), `shadow` says whether a visible "Apply now" link/button sits inside a web component's shadow root.
Only links whose href has "/talentcommunity/apply/" followed by a numeric job id count as SAP apply links.
It returns True only when at least one SAP apply link exists, none of them is visible, and `shadow` is True. Every
other situation returns False: a visible SAP link (it is clicked as usual), no SAP link at all (the "Apply now"
dropdown flow of other tenants), or hidden SAP links with no visible shadow-root Apply. An empty / missing `info`
returns False.
