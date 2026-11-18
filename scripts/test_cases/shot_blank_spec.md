# A blank confirmation screenshot (JSA-223, a Greenhouse employer 11-05)

After a submit the runner saves a full-page screenshot of the confirmation page. a Greenhouse employer's Greenhouse page was already at
/confirmation with the thank-you text readable from the DOM, yet the PNG was white except for one blue link underline
(130 × 2 px on a 2940 × 1602 image): the text had not been painted yet.

`shot_blank(png_bytes)` → True when the image shows (almost) nothing: take the image's most common colour as the
background; a pixel is "ink" when any channel differs from the background by more than 16; the shot is blank when ink
pixels are fewer than 0.1 % of all pixels (0.001 × width × height). A real page with a few lines of text has far more ink
than that. A uniform image of any colour (white, black, grey) is blank. Unreadable / empty bytes → True (nothing usable).
Ink of any colour counts (dark text on white, white text on a dark background).
