/** Field label: 14px medium, with a required star or "(optional)". */
export function FieldLabel({
  htmlFor,
  children,
  required,
  optional,
}: {
  htmlFor: string;
  children: React.ReactNode;
  required?: boolean;
  optional?: boolean;
}) {
  return (
    <label htmlFor={htmlFor} className="block text-sm font-medium text-text-strong">
      {children}
      {required && (
        <>
          <span aria-hidden className="ml-0.5 text-fin-danger">
            *
          </span>
          <span className="sr-only"> (required)</span>
        </>
      )}
      {optional && (
        <span className="ml-1 font-normal text-text-muted">(optional)</span>
      )}
    </label>
  );
}
