import { NextResponse } from "next/server";
import { isClerkEnabled } from "./app/lib/clerk";

const withClerk = () => {
  const { clerkMiddleware, createRouteMatcher } = require("@clerk/nextjs/server");
  const routeMatcher = createRouteMatcher(["/chat(.*)", "/"]);
  return clerkMiddleware((auth: () => { protect: () => void }, request: { nextUrl: { pathname: string } }) => {
    if (routeMatcher(request)) auth().protect();
  });
};

export default isClerkEnabled
  ? withClerk()
  : () => NextResponse.next();

export const config = {
  matcher: ["/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|png|gif|svg|ico|woff2?|ttf|map)).*)", "/(api|trpc)(.*)"],
};
