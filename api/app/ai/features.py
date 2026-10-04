"""What the assistant can help with. Each workspace's admins tick the ones they want;
nothing is on until they do."""

from __future__ import annotations

# key -> (English label, Bangla label). The web app has the same keys in its i18n files.
FEATURES: dict[str, tuple[str, str]] = {
    "ask": ("Answer questions about the workspace's own data", "ওয়ার্কস্পেসের নিজের তথ্য নিয়ে প্রশ্নের উত্তর"),
    "documents": (
        "Answer from policies and documents, with the passages",
        "নীতিমালা ও ডকুমেন্ট থেকে উত্তর, উদ্ধৃতিসহ",
    ),
    "brief": ("A weekly brief for owners and managers", "মালিক ও ম্যানেজারদের জন্য সাপ্তাহিক সারসংক্ষেপ"),
    "actions": (
        "Offer to do things (create tasks, ask for leave…), only after the person confirms",
        "কাজ করে দেওয়ার প্রস্তাব (কাজ তৈরি, ছুটির আবেদন…), শুধু ব্যক্তি নিশ্চিত করলে",
    ),
    "writing": (
        "Help writing announcements, tasks and documents, and translating them",
        "ঘোষণা, কাজ ও ডকুমেন্ট লিখতে এবং অনুবাদে সাহায্য",
    ),
    "automations": ("Turn plain words into automations to review", "সাধারণ ভাষা থেকে অটোমেশন তৈরি, যাচাইয়ের জন্য"),
    "signals": ("Early-warning signals for managers", "ম্যানেজারদের জন্য আগাম সতর্কসংকেত"),
}
