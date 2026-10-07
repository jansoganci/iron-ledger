export default function RegisterPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-canvas px-4">
      <p className="text-base text-text-primary text-center max-w-[400px]">
        Sign-ups are closed. Email{" "}
        <a
          href="mailto:john@truecost.lol"
          className="text-text-primary underline decoration-dotted underline-offset-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent rounded"
        >
          john@truecost.lol
        </a>{" "}
        for access.
      </p>
    </div>
  );
}
