import { NextResponse } from "next/server";
import { db } from "@/lib/db";

export async function GET(req: Request, { params }: { params: { ticketId: string } }) {
  try {
    const ticketId = params.ticketId;
    const ticket = await db.ticket.findUnique({
      where: {
        id: ticketId,
      },
    });

    if (!ticket) {
      return new NextResponse("Ticket not found", { status: 404 });
    }

    return NextResponse.json(ticket);
  } catch (error) {
    console.error("[TICKET_GET]", error);
    return new NextResponse("Internal error", { status: 500 });
  }
}

export async function DELETE(
  req: Request,
  { params }: { params: { ticketId: string } }
) {
  try {
    // Corrected params.id to params.ticketId and fixed potential ReferenceError
    const ticket = await db.ticket.delete({
      where: {
        id: params.ticketId,
      },
    });

    return NextResponse.json(ticket);
  } catch (error) {
    console.error("[TICKET_DELETE]", error);
    return new NextResponse("Internal error", { status: 500 });
  }
}
