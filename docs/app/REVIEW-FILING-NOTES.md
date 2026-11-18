# Review filing feedback

Approve and Skip save a decision label first. The cloud filing workflow then saves the durable folder record and closes the review card. Previously the card retained its action buttons on reload, making that delay look like a failed save.

Both actions now show a received-and-filing status, hide the repeated action buttons, and poll the issue state without resubmitting a choice. Confirmed closed cards leave the review list. Slow or unavailable status checks explicitly retain the recorded decision and tell the owner to refresh folders. This does not claim a video is published or physically deleted.

Eleven automated UI/model checks pass, including approval, skip, read-back failure and no repeated mutation. Phone and laptop layout checks pass. No owner choice is changed by this UI fix.
