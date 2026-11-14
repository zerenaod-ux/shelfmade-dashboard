# Automated content studio

Code for three automated channels. Plans, notes and private operating documents are kept elsewhere.

## 2026-11-13 — Content Engine Approve/Skip review (append-only)

The Content Engine section of the phone Review tab now has the same two-tap Approve/Skip button classes and layout as the other channels. Approve requests filing under Saved; Skip requests filing under Delete as a holding folder. Saved/Delete views show the retained video references. Actual folder commits are handled in the separate Content Engine repository before its review card closes. This change neither publishes nor deletes media and does not modify the other channels' decision handlers, queues or accounts.

The app changes are on a review branch pending deployment. The Pages deployment job is restricted to the existing master branch so feature-branch previews cannot deploy the shared app. A mocked phone-browser test covers confirmation, both actions, folder separation and failure recovery without altering any real review card. Backend and app must be deployed in that order; the backend creates its own decision labels and folders first. Existing phone access needs Issues write for Content Engine, as before. See the companion Content Engine review-folders change for storage details.


## 2026-11-13 — Approve/Skip folders deployed (append-only)

Owner authorized deployment. The Content Engine folder handler and matching phone controls are merged and live. Backend setup completed successfully; the shared app Pages deployment completed successfully. Live read-only verification confirmed Content Engine Approve/Skip cards and working Saved/Delete views. Approve retains the video under Saved for future publishing; Skip retains it under Delete for possible later deletion. Neither action publishes or deletes media. No existing video was approved/skipped during verification. The 27 backend tests and mocked phone-browser flow passed in GitHub before deployment. Existing channel decision code is unchanged. Reopen or refresh the phone app to load the updated shell.
