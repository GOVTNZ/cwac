# Rendered object audit

The rendered object audit counts occurrences of `[object` in the loaded page's
rendered body text. This can identify JavaScript values accidentally shown to
visitors, such as `[object Object]` or `[object Promise]`.

Enable the plugin in your audit configuration:

```json
"rendered_object_audit": {
  "class_name": "RenderedObjectAudit",
  "enabled": true
}
```

The audit uses `document.body.innerText`, so it excludes script and style
contents, HTML attributes, and text hidden by CSS. It checks the current
rendered page after CWAC's configured page-load delay. Matches are
case-sensitive. It does not check for `null` or `undefined`.

Results are written to `rendered_object_audit.csv`. Each page produces a row
with the usual page information, `audit_type`, and `num_issues` (the number of
occurrences). A page without matches has `num_issues` set to `0`.

Review matches manually: documentation or code examples can legitimately contain
`[object`. The audit detects likely content bugs; it does not establish a WCAG
failure. It does not inspect iframe documents or shadow DOM.
