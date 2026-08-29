const sampleButton = document.querySelector("[data-sample]");
const brief = document.querySelector("#brief");

if (sampleButton && brief) {
  sampleButton.addEventListener("click", () => {
    brief.value = sampleButton.dataset.sample;
    brief.focus();
  });
}

if (window.location.hash === "#report") {
  document.querySelector("#report")?.scrollIntoView({ behavior: "smooth" });
}
