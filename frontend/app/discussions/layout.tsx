/**
 * Discussion state is owned by the root layout so replacing this route segment
 * cannot interrupt an active SSE request.
 */

export default function DiscussionsLayout({ children }: { children: React.ReactNode }) {
  return children;
}
